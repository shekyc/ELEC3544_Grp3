"""Frozen temporal holdout orchestration; development artifacts remain immutable."""

import json
import tomllib
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from musk_sentiment.analysis.minute import MinuteStore, build_minute_events, describe_minutes
from musk_sentiment.config import load_config
from musk_sentiment.data.corpus import read_posts
from musk_sentiment.models.minute import evaluate_minute_models
from musk_sentiment.nlp.pipeline import build_user_prompt
from musk_sentiment.schemas import MinuteEvent, NLPRecord
from musk_sentiment.utils.io import digest, save_records, write_json


def merge_market_manifests(previous, current, output, boundary="2022-01-01"):
    """Reference immutable files, retaining old history strictly before the test boundary."""
    tickers = {p.parent.name for root in (previous, current) for p in root.glob("*/manifest.json")}
    for ticker in sorted(tickers):
        files, sources = [], {}
        for root, is_old in [(previous, True), (current, False)]:
            path = root / ticker / "manifest.json"
            if not path.exists():
                continue
            report = json.loads(path.read_text())
            if report["synthetic"] or report["interval"] != "1min":
                raise ValueError("Require empirical minute histories")
            sources[str(path)] = digest(path.read_bytes())
            files.extend(
                f for f in report["daily_files"] if (Path(f["path"]).stem < boundary) == is_old
            )
        days = [Path(f["path"]).stem for f in files]
        if len(days) != len(set(days)):
            raise ValueError("Duplicate dates in combined market history")
        write_json(
            output / ticker / "manifest.json",
            {
                "ticker": ticker,
                "interval": "1min",
                "synthetic": False,
                "daily_files": sorted(files, key=lambda f: Path(f["path"]).stem),
                "rows": sum(f["rows"] for f in files),
                "source_manifest_sha256": sources,
                "policy": "Old files before boundary; new files on/after boundary; no filling",
            },
        )


def verify_frozen(freeze_path):
    freeze = json.loads(freeze_path.read_text())
    for field in ["baseline_sha256", "frozen_files"]:
        for name, expected in freeze[field].items():
            if digest(Path(name).read_bytes()) != expected:
                raise ValueError(f"Frozen artifact changed: {name}")
    return sum(len(freeze[x]) for x in ["baseline_sha256", "frozen_files"])


def run_holdout(
    posts_path, nlp_path, market, project, minute_config, training, prior_nlp, freeze_path, output
):
    """Train only before the cutoff; reuse all fixed model and outcome definitions."""
    if (output / "manifest.json").exists():
        raise ValueError("Completed holdout exists; choose a separate output")
    preserved = verify_frozen(freeze_path)
    config = load_config(project)
    settings = tomllib.loads(minute_config.read_text())["minute"]
    original_settings = tomllib.loads(Path("configs/minute.toml").read_text())["minute"]
    mutable = {"market_end", "test_start"}
    if {k: v for k, v in settings.items() if k not in mutable} != {
        k: v for k, v in original_settings.items() if k not in mutable
    }:
        raise ValueError("Non-date analysis settings changed")
    if config["assets"] != load_config(Path("configs/project.toml"))["assets"]:
        raise ValueError("Frozen asset universe changed")
    cutoff = datetime.fromisoformat(config["research"]["start"]).replace(tzinfo=UTC)
    end = datetime.fromisoformat(config["research"]["end"]).replace(tzinfo=UTC)
    if settings["test_start"] != config["research"]["start"]:
        raise ValueError("Test boundary mismatch")
    posts = read_posts(posts_path)
    if not posts or any(not cutoff <= p.created_at < end for p in posts):
        raise ValueError("Holdout post outside declared test window")
    records = [NLPRecord.model_validate(r) for r in json.loads(nlp_path.read_text())]
    prior = [NLPRecord.model_validate(r) for r in json.loads(prior_nlp.read_text())]
    old_posts = read_posts(Path("data/processed/study/posts.json"))
    if {p.post_id for p in old_posts} != {r.output.post_id for r in prior} or any(
        p.created_at >= cutoff for p in old_posts
    ):
        raise ValueError("Invalid mention history")
    if {p.post_id for p in posts} & {p.post_id for p in old_posts}:
        raise ValueError("Holdout overlaps development corpus")
    versions = {
        (r.model, r.prompt_version, r.parameters["reasoning_effort"]) for r in prior + records
    }
    if len(versions) != 1:
        raise ValueError("Frozen NLP setup changed")
    post_map = {p.post_id: p for p in posts}
    for r in records:
        if r.output.post_id not in post_map or r.input_sha256 != digest(
            build_user_prompt(post_map[r.output.post_id], config["assets"]).encode()
        ):
            raise ValueError("Holdout NLP input mismatch")
    counts = Counter(a.ticker for r in prior for a in r.output.assets)
    store = MinuteStore(market)
    events, rejected, assignments = build_minute_events(
        posts, records, config["assets"], store, settings, prior_mentions=counts
    )
    old_events = [
        MinuteEvent.model_validate(r) for r in json.loads((training / "events.json").read_text())
    ]
    if any(r.posted_at >= cutoff for r in old_events):
        raise ValueError("Development events overlap test period")
    save_records(output / "events.json", events)
    write_json(output / "assignments.json", assignments)
    write_json(output / "rejections.json", rejected)
    for name, unit in [("descriptive", "overlap"), ("day_cluster_sensitivity", "day")]:
        write_json(output / f"{name}.json", describe_minutes(events, settings, unit))
    horizons = {}
    for r in events:
        horizons.setdefault((r.ticker, r.cohort, r.post_id), set()).add(r.horizon_minutes)
    common = [
        r
        for r in events
        if horizons[r.ticker, r.cohort, r.post_id] == set(settings["horizons_minutes"])
    ]
    write_json(output / "common_horizon_sensitivity.json", describe_minutes(common, settings))
    models = evaluate_minute_models(old_events + events, settings, test_only=True)
    models["policy"] = (
        "Frozen hyperparameters; fit only pre-2022 events after overlap purge; evaluate 2022 only"
    )
    models["caveats"][0] = (
        "2022 was reserved before inspecting its outcomes; 2020–2021 were used in development"
    )
    write_json(output / "models.json", models)
    write_json(
        output / "coverage.json",
        {
            "posts": len(posts),
            "assigned_post_assets": len(assignments),
            "events": len(events),
            "rejection_reasons": dict(Counter(r["reason"] for r in rejected)),
            "accepted": [
                {"ticker": k[0], "cohort": k[1], "horizon_minutes": k[2], "events": n}
                for k, n in sorted(
                    Counter((r.ticker, r.cohort, r.horizon_minutes) for r in events).items()
                )
            ],
            "prior_mentions": dict(counts),
        },
    )
    input_paths = [
        posts_path,
        nlp_path,
        project,
        minute_config,
        training / "events.json",
        prior_nlp,
        freeze_path,
    ]
    manifest = {
        "synthetic": False,
        "events": len(events),
        "rejected": len(rejected),
        "settings": settings,
        "test_start": cutoff.isoformat(),
        "test_end_exclusive": end.isoformat(),
        "input_sha256": {str(p): digest(p.read_bytes()) for p in input_paths},
        "market_manifest_sha256": {
            t: digest((market / t / "manifest.json").read_bytes()) for t in store.manifests
        },
        "source_sha256": {
            str(p): digest(p.read_bytes())
            for p in [
                Path(__file__),
                Path("src/musk_sentiment/analysis/minute.py"),
                Path("src/musk_sentiment/models/minute.py"),
            ]
        },
        "prior_mentions": dict(counts),
        "frozen_files_preserved": preserved,
        "limitations": [
            "Modern LLM historical knowledge can leak despite temporal downstream holdout",
            "Observed post corpus may be incomplete; contemporary adjusted price history",
            "Retrospective association is not causal evidence",
        ],
    }
    verify_frozen(freeze_path)
    write_json(output / "manifest.json", manifest)
    return manifest
