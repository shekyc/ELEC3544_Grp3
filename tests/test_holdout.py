"""Temporal holdout boundaries and immutable historical data selection."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from musk_sentiment.analysis.holdout import merge_market_manifests, verify_frozen
from musk_sentiment.models.minute import evaluate_minute_models, split_minute_rows
from musk_sentiment.utils.io import digest, write_json


def test_combined_market_retains_old_pretest_dates(tmp_path):
    old, new, combined = [tmp_path / name for name in ["old", "new", "combined"]]
    for root, days in [(old, ["2021-12-31", "2022-01-03"]), (new, ["2022-01-03"])]:
        write_json(
            root / "TSLA/manifest.json",
            {
                "ticker": "TSLA",
                "synthetic": False,
                "interval": "1min",
                "daily_files": [
                    {"path": str(root / f"{d}.json"), "sha256": "fixture", "rows": 1} for d in days
                ],
            },
        )
    before = (old / "TSLA/manifest.json").read_bytes()
    merge_market_manifests(old, new, combined)
    result = json.loads((combined / "TSLA/manifest.json").read_text())
    assert [f["path"] for f in result["daily_files"]] == [
        str(old / "2021-12-31.json"),
        str(new / "2022-01-03.json"),
    ]
    assert before == (old / "TSLA/manifest.json").read_bytes()


def test_freeze_detects_mutation(tmp_path):
    artifact = tmp_path / "old.json"
    artifact.write_text("original")
    freeze = tmp_path / "freeze.json"
    write_json(
        freeze,
        {"baseline_sha256": {str(artifact): digest(artifact.read_bytes())}, "frozen_files": {}},
    )
    assert verify_frozen(freeze) == 1
    artifact.write_text("changed")
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        verify_frozen(freeze)


def test_year_boundary_outcome_purge_and_test_only_phase():
    def row(name, posted, entry, end):
        return SimpleNamespace(
            event_id=name,
            posted_at=datetime.fromisoformat(posted).replace(tzinfo=UTC),
            entry_at=datetime.fromisoformat(entry).replace(tzinfo=UTC),
            end_at=datetime.fromisoformat(end).replace(tzinfo=UTC),
            ticker="TSLA",
            cohort="next_opening",
            horizon_minutes=5,
            features=None,
        )

    old = row("old", "2021-12-30", "2021-12-30T14:30", "2021-12-30T14:35")
    crosses = row("crosses", "2021-12-31T23:00", "2022-01-03T14:30", "2022-01-03T14:35")
    test = row("test", "2022-01-01", "2022-01-03T14:30", "2022-01-03T14:35")
    train, held = split_minute_rows([old, crosses, test], datetime(2022, 1, 1, tzinfo=UTC))
    assert train == [old] and held == [test]
    result = evaluate_minute_models(
        [old, crosses, test],
        {"validation_start": "2021-01-01", "test_start": "2022-01-01"},
        test_only=True,
    )
    assert len(result["skipped"]) == 4
    assert {r["phase"] for r in result["skipped"]} == {"test"}
