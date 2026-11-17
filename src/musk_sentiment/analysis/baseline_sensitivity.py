"""Separate baseline-availability sensitivity, retaining frozen V7 and forward-window rules."""

import json
import tomllib
from collections import Counter
from pathlib import Path

from musk_sentiment.analysis.minute import (
    MinuteStore,
    build_minute_events,
    describe_minutes,
    measurements,
)
from musk_sentiment.config import load_config
from musk_sentiment.data.corpus import read_posts
from musk_sentiment.nlp.pipeline import build_user_prompt
from musk_sentiment.schemas import NLPRecord
from musk_sentiment.utils.io import digest, save_records, write_json


def run_sensitivity(output=Path("results/baseline_sensitivity_v7")):
    """Only relax baseline availability; never fill prices, benchmark windows or predictors."""
    if (output / "manifest.json").exists():
        raise ValueError("Completed sensitivity exists; choose a separate output")
    roots = [
        Path(x)
        for x in [
            "results/study_minute_v7",
            "results/study_minute_v7_2022",
            "results/validation_minute_v7",
            "results/validation_minute_v7_2022",
            "data/processed/nlp_sol_v7",
            "data/processed/nlp_sol_v7_2022",
        ]
    ]
    frozen = {
        str(p): digest(p.read_bytes()) for root in roots for p in root.rglob("*") if p.is_file()
    }
    write_json(output / "baseline_preservation.json", frozen)
    assets = load_config(Path("configs/project.toml"))["assets"]
    prior = Counter()
    comparisons = []
    for period, posts_file, nlp_dir, market, config, baseline in [
        ("2020_2021", "study", "nlp_sol_v7", "market_minute_v7", "minute", "study_minute_v7"),
        (
            "2022",
            "study_2022",
            "nlp_sol_v7_2022",
            "market_minute_combined_2022",
            "minute_2022",
            "study_minute_v7_2022",
        ),
    ]:
        target = output / period
        paths = [
            Path(f"data/processed/{posts_file}/posts.json"),
            Path(f"data/processed/{nlp_dir}/sentiments.json"),
            Path(f"configs/{config}.toml"),
        ]
        posts = read_posts(paths[0])
        nlp = [NLPRecord.model_validate(r) for r in json.loads(paths[1].read_text())]
        by_id = {p.post_id: p for p in posts}
        for r in nlp:
            if r.input_sha256 != digest(
                build_user_prompt(by_id[r.output.post_id], assets).encode()
            ):
                raise ValueError("NLP input mismatch")
        settings = tomllib.loads(paths[2].read_text())["minute"]
        store = MinuteStore(Path(f"data/processed/{market}"))
        events, rejected, assignments = build_minute_events(
            posts, nlp, assets, store, settings, prior_mentions=prior, allow_missing_baseline=True
        )
        old = {
            r["event_id"]: r
            for r in json.loads(Path(f"results/{baseline}/events.json").read_text())
        }
        new = {r.event_id: r for r in events}
        if not old.keys() <= new.keys():
            raise ValueError("Sensitivity removed an existing event")
        for key, row in old.items():
            if row != new[key].model_dump(mode="json"):
                raise ValueError("Sensitivity changed an existing event")
        added = [r for r in events if r.event_id not in old]
        for r in added:
            if r.baseline_to_end_return is not None or r.features is not None:
                raise ValueError("Unexpected added event: baseline/features must be unavailable")
            measured = measurements(store.window(r.ticker, r.entry_at, r.horizon_minutes))
            if any(getattr(r, k) != v for k, v in measured.items()):
                raise ValueError("Outcome replay mismatch")
        eligible_old = {k for k, r in old.items() if r["features"] is not None}
        eligible_new = {r.event_id for r in events if r.features is not None}
        if eligible_old != eligible_new:
            raise ValueError("Unexpected predictive sample change")
        save_records(target / "events.json", events)
        save_records(target / "added_events.json", added)
        write_json(target / "rejections.json", rejected)
        write_json(target / "assignments.json", assignments)
        for name, unit in [("descriptive", "overlap"), ("day_cluster_sensitivity", "day")]:
            write_json(target / f"{name}.json", describe_minutes(events, settings, unit))
        old_summary = json.loads(
            Path(f"results/{baseline}/day_cluster_sensitivity.json").read_text()
        )["summaries"]
        new_summary = json.loads((target / "day_cluster_sensitivity.json").read_text())["summaries"]

        def key(r):
            return (r["ticker"], r["cohort"], r["horizon_minutes"], r["metric"])

        a, b = {key(r): r for r in old_summary}, {key(r): r for r in new_summary}
        comparisons.extend(
            {
                "period": period,
                "ticker": k[0],
                "cohort": k[1],
                "horizon_minutes": k[2],
                "metric": k[3],
                "frozen": a.get(k),
                "sensitivity": b.get(k),
            }
            for k in sorted(a.keys() | b.keys())
        )
        write_json(
            target / "manifest.json",
            {
                "settings": settings,
                "frozen_events": len(old),
                "sensitivity_events": len(events),
                "added_events": len(added),
                "rejected": len(rejected),
                "added_by_asset": dict(Counter(r.ticker for r in added)),
                "prior_mentions": dict(prior),
                "existing_events_identical": True,
                "prediction_eligible_ids_unchanged": True,
                "input_sha256": {str(p): digest(p.read_bytes()) for p in paths},
                "market_manifest_sha256": {
                    t: digest((Path(f"data/processed/{market}") / t / "manifest.json").read_bytes())
                    for t in store.manifests
                },
            },
        )
        prior.update(a.ticker for r in nlp for a in r.output.assets)
        print(period, len(old), "->", len(events), "added", len(added), flush=True)
    write_json(output / "comparison.json", comparisons)
    if any(digest(Path(p).read_bytes()) != h for p, h in frozen.items()):
        raise ValueError("Frozen artifact changed")
    write_json(
        output / "manifest.json",
        {
            "policy": (
                "Allow absent immediate baseline; keep complete forward own/benchmark bars, "
                "boundaries and no filling. Baseline-dependent returns and incomplete "
                "pre-post features remain null."
            ),
            "prediction": "Eligible event IDs and existing rows unchanged; no model refit needed",
            "partial_pre_window": (
                "Already allowed for descriptive outcomes if immediate baseline "
                "exists; predictors require all five prior minutes"
            ),
            "frozen_files_preserved": len(frozen),
            "source_sha256": {
                str(p): digest(p.read_bytes())
                for p in [
                    Path(__file__),
                    Path("src/musk_sentiment/analysis/minute.py"),
                    Path("src/musk_sentiment/schemas.py"),
                ]
            },
            "limitations": [
                "Post-hoc sensitivity, not a new untouched holdout",
                "No causal claims; missing-minute selection persists",
                "Pretrend/control checks retain their original baseline requirements",
            ],
        },
    )


if __name__ == "__main__":
    run_sensitivity()
