"""Frozen minute validation: event-time paths, past-only matched controls and influence checks."""

import json
import math
import tomllib
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from musk_sentiment.analysis.minute import (
    MINUTE,
    NY,
    MinuteStore,
    SessionClock,
    adjust_fdr,
    measurements,
)
from musk_sentiment.schemas import MinuteEvent
from musk_sentiment.utils.io import digest, write_json

METRICS = [
    "forward_return",
    "benchmark_adjusted_return",
    "relative_volume",
    "relative_trade_count",
    "relative_volatility",
]


def time_value(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def day_key(entry, cohort):
    return entry.astimezone(UTC if cohort == "crypto_24h" else NY).date().isoformat()


def observed_posts_between(times, start, end, own=None):
    """Inclusive exclusion, allowing the event's own timestamp exactly once."""
    count = bisect_right(times, end) - bisect_left(times, start)
    if own is not None and start <= own <= end:
        count -= 1
    return count


def bootstrap_mean(values, settings):
    values = np.asarray(values, dtype=float)
    if len(values) < 5:
        return None
    rng = np.random.default_rng(settings["seed"])
    boot = rng.choice(values, (settings["bootstrap_repetitions"], len(values)), replace=True).mean(
        axis=1
    )
    return np.quantile(boot, [0.025, 0.975]).tolist()


def sign_p(values):
    from scipy.stats import binomtest

    values = np.asarray(values)
    nonzero = values[values != 0]
    if len(nonzero) < 5:
        return None
    return float(binomtest(int(sum(nonzero > 0)), len(nonzero), 0.5).pvalue)


def event_profiles(assignments, store, clock, settings):
    """Balanced paths; zero is publication-minute start, except delayed next-opening paths."""
    paths, rejected = [], []
    before, after = settings["pre_minutes"], settings["post_minutes"]
    for assignment in assignments:
        ticker, cohort = assignment["ticker"], assignment["cohort"]
        posted = time_value(assignment["posted_at"])
        delayed = cohort == "next_opening"
        anchor = (
            time_value(assignment["entry_at"])
            if delayed
            else posted.replace(second=0, microsecond=0)
        )
        start = anchor if delayed else anchor - (before + 1) * MINUTE
        try:
            if not clock.same_session_window(start, anchor + after * MINUTE, cohort):
                raise ValueError("Balanced profile crosses session boundary")
            bars = store.window(ticker, start, after if delayed else before + after + 1)
            if delayed:
                offsets = list(range(0, after + 1))
                prices = [bars[0].o] + [b.c for b in bars]
                reference = bars[0].o
                pre_return = None
            else:
                offsets = list(range(-before, after + 1))
                prices = [b.c for b in bars]
                reference = prices[before]
                pre_return = reference / prices[0] - 1
            path = {
                **assignment,
                "anchor_at": anchor.isoformat(),
                "day": day_key(anchor, cohort),
                "offset_minutes": offsets,
                "cumulative_return": [p / reference - 1 for p in prices],
                "pre_return": pre_return,
                "post_5_return": prices[offsets.index(5)] / reference - 1,
                "post_15_return": prices[offsets.index(15)] / reference - 1,
                "post_30_return": prices[offsets.index(30)] / reference - 1,
                "post_60_return": prices[offsets.index(60)] / reference - 1,
                "publication_offset_seconds": None
                if delayed
                else (posted - anchor).total_seconds(),
                "activity_bins": [],
            }
            if not delayed:
                reference_bars = store.window(
                    ticker, anchor - before * MINUTE, before - settings["matching_pre_end_minutes"]
                )
                reference_activity = measurements(reference_bars)
                for lo, hi in [(-30, -15), (-15, 0), (0, 5), (5, 15), (15, 30), (30, 60)]:
                    values = measurements(store.window(ticker, anchor + lo * MINUTE, hi - lo))
                    bin_result = {"start": lo, "end": hi}
                    for name in ["volume", "trade_count"]:
                        denom = reference_activity[name] / len(reference_bars)
                        bin_result[name + "_rate_ratio"] = (
                            values[name] / (hi - lo) / denom if denom > 0 else None
                        )
                    denom = reference_activity["realized_volatility"] / math.sqrt(
                        len(reference_bars)
                    )
                    bin_result["volatility_rate_ratio"] = (
                        values["realized_volatility"] / math.sqrt(hi - lo) / denom
                        if denom > 0
                        else None
                    )
                    path["activity_bins"].append(bin_result)
            paths.append(path)
        except ValueError as exc:
            if "Missing required" not in str(exc) and "crosses session" not in str(exc):
                raise
            rejected.append({**assignment, "reason": str(exc)})
    summaries = []
    groups = defaultdict(list)
    for p in paths:
        groups[(p["ticker"], p["cohort"])].append(p)
    for (ticker, cohort), group in sorted(groups.items()):
        days = defaultdict(list)
        for p in group:
            days[p["day"]].append(p)
        day_paths = np.array(
            [np.mean([p["cumulative_return"] for p in rows], axis=0) for rows in days.values()]
        )
        mean = day_paths.mean(axis=0)
        low, high = None, None
        if len(days) >= 5:
            rng = np.random.default_rng(settings["seed"])
            ids = rng.integers(0, len(days), (settings["bootstrap_repetitions"], len(days)))
            boot = day_paths[ids].mean(axis=1)
            low, high = np.quantile(boot, [0.025, 0.975], axis=0).tolist()
        summary = {
            "ticker": ticker,
            "cohort": cohort,
            "events": len(group),
            "days": len(days),
            "offset_minutes": group[0]["offset_minutes"],
            "mean_path": mean.tolist(),
            "ci_low": low,
            "ci_high": high,
            "tests": [],
            "activity_bins": [],
        }
        for metric in [
            "pre_return",
            "post_5_return",
            "post_15_return",
            "post_30_return",
            "post_60_return",
        ]:
            if group[0][metric] is None:
                continue
            values = [np.mean([p[metric] for p in rows]) for rows in days.values()]
            summary["tests"].append(
                {
                    "metric": metric,
                    "mean": float(np.mean(values)),
                    "median_day": float(np.median(values)),
                    "ci": bootstrap_mean(values, settings),
                    "p": sign_p(values),
                }
            )
        if group[0]["activity_bins"]:
            for i, item in enumerate(group[0]["activity_bins"]):
                out = {"start": item["start"], "end": item["end"]}
                for metric in [
                    "volume_rate_ratio",
                    "trade_count_rate_ratio",
                    "volatility_rate_ratio",
                ]:
                    values = [
                        np.mean(
                            [
                                p["activity_bins"][i][metric]
                                for p in rows
                                if p["activity_bins"][i][metric] is not None
                            ]
                        )
                        for rows in days.values()
                        if any(p["activity_bins"][i][metric] is not None for p in rows)
                    ]
                    out[metric] = {
                        "mean": float(np.mean(values)) if values else None,
                        "ci": bootstrap_mean(values, settings),
                        "days": len(values),
                    }
                summary["activity_bins"].append(out)
        summaries.append(summary)
    adjust_fdr([t for s in summaries for t in s["tests"]], "p", "q")
    return {
        "paths": paths,
        "summaries": summaries,
        "rejections": rejected,
        "timing": (
            "Immediate profiles: zero is publication-minute start and reference "
            "is preceding close; publication is within [0,1) minute. Next-opening "
            "profiles: zero is opening, no pre-publication path inferred."
        ),
        "limitations": (
            "Balanced -30/+60 sample differs from primary windows; profile "
            "intervals are pointwise, not simultaneous; profiles are descriptive, "
            "not prediction targets."
        ),
    }


def preconditions(store, clock, ticker, benchmark, entry, posted, cohort, settings):
    """Match pre-publication conditions, leaving an unconditioned five-minute lead-in."""
    end = (
        clock.previous_close(posted)
        if cohort == "next_opening"
        else posted.replace(second=0, microsecond=0)
    )
    start = end - settings["pre_minutes"] * MINUTE
    minutes = settings["pre_minutes"] - settings["matching_pre_end_minutes"]
    expected = "regular" if cohort == "next_opening" else cohort
    if not clock.same_session_window(start, start + minutes * MINUTE, expected):
        raise ValueError("Precondition window crosses session")
    own = measurements(store.window(ticker, start, minutes))
    features = [
        own["forward_return"],
        math.log1p(own["volume"]),
        math.log1p(own["trade_count"]),
        math.log(max(own["realized_volatility"], 1e-8)),
    ]
    if benchmark != ticker:
        features.append(measurements(store.window(benchmark, start, minutes))["forward_return"])
    return np.array(features), start + minutes * MINUTE


def matching_distances(actual, candidates):
    """Robust control-pool scaling; no post-window outcomes enter matching."""
    matrix = np.asarray(candidates)
    scale = np.quantile(matrix, 0.75, axis=0) - np.quantile(matrix, 0.25, axis=0)
    fallback = np.std(matrix, axis=0)
    scale = np.where(scale > 1e-10, scale, np.where(fallback > 1e-10, fallback, 1.0))
    return np.sqrt(np.mean(((matrix - actual) / scale) ** 2, axis=1))


def matched_placebos(events, posts, store, clock, benchmarks, settings):
    times = sorted(p.created_at for p in posts)
    records, rejected = [], []
    for event in events:
        ticker, cohort, horizon = event.ticker, event.cohort, event.horizon_minutes
        base = {
            "event_id": event.event_id,
            "post_id": event.post_id,
            "ticker": ticker,
            "cohort": cohort,
            "horizon_minutes": horizon,
            "day": day_key(event.entry_at, cohort),
        }
        try:
            actual_features, feature_end = preconditions(
                store,
                clock,
                ticker,
                benchmarks[ticker],
                event.entry_at,
                event.posted_at,
                cohort,
                settings,
            )
            refs = clock.references(
                event.entry_at, cohort, settings["candidate_prior_days_or_sessions"]
            )
            pool = []
            rejection_counts = defaultdict(int)
            for entry in refs:
                if entry.date().isoformat() < settings["control_start"]:
                    rejection_counts["outside observed post corpus period"] += 1
                    continue
                pseudo_post = entry - timedelta(seconds=event.entry_delay_seconds)
                if cohort == "crypto_24h" and (entry.weekday() >= 5) != (
                    event.entry_at.weekday() >= 5
                ):
                    rejection_counts["weekday/weekend mismatch"] += 1
                    continue
                if cohort == "next_opening":
                    classified, opening, _ = clock.classify(pseudo_post)
                    if classified != cohort or opening != entry:
                        rejection_counts["different closed-market timing"] += 1
                        continue
                if not clock.same_session_window(entry, entry + horizon * MINUTE, cohort):
                    rejection_counts["session mismatch"] += 1
                    continue
                start_exclusion = pseudo_post - settings["exclude_other_posts_pre_minutes"] * MINUTE
                end_exclusion = entry + settings["exclude_other_posts_post_minutes"] * MINUTE
                if start_exclusion.date().isoformat() < settings["control_start"]:
                    rejection_counts["exclusion window outside observed corpus period"] += 1
                    continue
                if observed_posts_between(times, start_exclusion, end_exclusion):
                    rejection_counts["observed corpus post near placebo"] += 1
                    continue
                if entry + horizon * MINUTE >= event.posted_at:
                    rejection_counts["control not strictly historical"] += 1
                    continue
                try:
                    features, past_end = preconditions(
                        store,
                        clock,
                        ticker,
                        benchmarks[ticker],
                        entry,
                        pseudo_post,
                        cohort,
                        settings,
                    )
                    # Availability is checked, but outcome VALUES never enter the distance/ranking.
                    bars = store.window(ticker, entry, horizon)
                    values = measurements(bars)
                    benchmark_return = None
                    if benchmarks[ticker] != ticker:
                        benchmark_return = measurements(
                            store.window(benchmarks[ticker], entry, horizon)
                        )["forward_return"]
                    pool.append(
                        {
                            "entry": entry,
                            "features": features,
                            "feature_end": past_end,
                            "values": values,
                            "benchmark_return": benchmark_return,
                        }
                    )
                except ValueError as exc:
                    if "Missing required" not in str(exc) and "Precondition window" not in str(exc):
                        raise
                    rejection_counts[str(exc)] += 1
            if len(pool) < settings["minimum_candidate_pool"]:
                rejected.append(
                    {
                        **base,
                        "reason": "Insufficient eligible placebo pool",
                        "candidate_pool": len(pool),
                        "candidate_rejections": dict(rejection_counts),
                    }
                )
                continue
            distances = matching_distances(actual_features, [p["features"] for p in pool])
            order = sorted(range(len(pool)), key=lambda i: (distances[i], pool[i]["entry"]))
            selected = [i for i in order if distances[i] <= settings["rms_caliper"]][
                : settings["matched_controls"]
            ]
            if len(selected) < settings["minimum_matched_controls"]:
                rejected.append(
                    {
                        **base,
                        "reason": "Insufficient controls within predeclared caliper",
                        "candidate_pool": len(pool),
                        "within_caliper": len(selected),
                    }
                )
                continue
            controls = [pool[i] for i in selected]
            control_values = {
                name: float(np.mean([c["values"][name] for c in controls]))
                for name in ["forward_return", "volume", "trade_count", "realized_volatility"]
            }
            effects = {"return_difference": event.forward_return - control_values["forward_return"]}
            if event.benchmark_adjusted_return is not None:
                control_adjusted = np.mean(
                    [c["values"]["forward_return"] - c["benchmark_return"] for c in controls]
                )
                effects["benchmark_adjusted_difference"] = event.benchmark_adjusted_return - float(
                    control_adjusted
                )
            for own_name, key in [
                ("volume", "volume_ratio"),
                ("trade_count", "trade_count_ratio"),
                ("realized_volatility", "volatility_ratio"),
            ]:
                denom = control_values[own_name]
                effects[key] = getattr(event, own_name) / denom if denom > 0 else None
            records.append(
                {
                    **base,
                    "actual_entry": event.entry_at.isoformat(),
                    "actual_posted_at": event.posted_at.isoformat(),
                    "features_end": feature_end.isoformat(),
                    "actual_features": actual_features.tolist(),
                    "candidate_pool": len(pool),
                    "controls": [
                        {
                            "entry": c["entry"].isoformat(),
                            "features_end": c["feature_end"].isoformat(),
                            "features": c["features"].tolist(),
                            "distance": float(distances[i]),
                            "values": c["values"],
                            "benchmark_return": c["benchmark_return"],
                        }
                        for i, c in zip(selected, controls, strict=True)
                    ],
                    "control_mean": control_values,
                    "effects": effects,
                }
            )
        except ValueError as exc:
            if "Missing required" not in str(exc) and "Precondition window" not in str(exc):
                raise
            rejected.append({**base, "reason": str(exc)})
    summaries = []
    groups = defaultdict(list)
    for r in records:
        groups[(r["ticker"], r["cohort"], r["horizon_minutes"])].append(r)
    for key, group in sorted(groups.items()):
        # Components join actual days that reuse a control date, accounting for shared controls.
        labels = {r["day"]: r["day"] for r in group}

        def root(day, labels=labels):
            while labels[day] != day:
                day = labels[day]
            return day

        owners = {}
        for r in group:
            dates = [r["day"]] + [
                day_key(time_value(c["entry"]), r["cohort"]) for c in r["controls"]
            ]
            for day in dates:
                if day in owners:
                    labels[root(r["day"])] = root(owners[day])
                else:
                    owners[day] = r["day"]
        for metric in [
            "return_difference",
            "benchmark_adjusted_difference",
            "volume_ratio",
            "trade_count_ratio",
            "volatility_ratio",
        ]:
            eligible = [r for r in group if r["effects"].get(metric) is not None]
            if not eligible:
                continue
            blocks = defaultdict(list)
            for r in eligible:
                blocks[root(r["day"])].append(r["effects"][metric])
            values = [np.mean(v) for v in blocks.values()]
            null = 1.0 if metric.endswith("ratio") else 0.0
            summaries.append(
                {
                    "ticker": key[0],
                    "cohort": key[1],
                    "horizon_minutes": key[2],
                    "metric": metric,
                    "events": len(eligible),
                    "independent_components": len(blocks),
                    "event_mean": float(np.mean([r["effects"][metric] for r in eligible])),
                    "component_mean": float(np.mean(values)),
                    "median_event": float(np.median([r["effects"][metric] for r in eligible])),
                    "ci": bootstrap_mean(values, settings),
                    "p": sign_p(np.array(values) - null),
                }
            )
    adjust_fdr(summaries, "p", "q")
    return {
        "records": records,
        "summaries": summaries,
        "rejections": rejected,
        "matching": (
            "Same asset/session/clock time; crypto weekday/weekend; prior 60 "
            "sessions/days; robust-scaled precondition distance; 5 nearest within "
            "RMS 2, minimum 3; minimum pool 10. No observed corpus posts in "
            "[-30,+60], extended for delayed opening."
        ),
        "inference": (
            "Actual days sharing control dates join into components; inference "
            "suppressed below five components. Nonrandom matching is "
            "observational, not a randomized placebo experiment."
        ),
    }


def influence_checks(events, posts, settings):
    times = sorted(p.created_at for p in posts)
    groups = defaultdict(list)
    for r in events:
        groups[(r.ticker, r.cohort, r.horizon_minutes)].append(r)
    result = []
    for key, group in sorted(groups.items()):
        isolated = [
            r
            for r in group
            if observed_posts_between(
                times,
                r.posted_at - settings["exclude_other_posts_pre_minutes"] * MINUTE,
                r.entry_at + settings["exclude_other_posts_post_minutes"] * MINUTE,
                r.posted_at,
            )
            == 0
        ]
        for metric in METRICS:
            eligible = [r for r in group if getattr(r, metric) is not None]
            if not eligible:
                continue
            days = defaultdict(list)
            for r in eligible:
                days[day_key(r.entry_at, r.cohort)].append(getattr(r, metric))
            means = {d: float(np.mean(v)) for d, v in days.items()}
            original = float(np.mean(list(means.values())))
            leave_out = {
                d: float(np.mean([v for k, v in means.items() if k != d]))
                for d in means
                if len(means) > 1
            }
            isolated_days = defaultdict(list)
            for r in isolated:
                if getattr(r, metric) is not None:
                    isolated_days[day_key(r.entry_at, r.cohort)].append(getattr(r, metric))
            iso = [float(np.mean(v)) for v in isolated_days.values()]
            null = 1 if metric.startswith("relative_") else 0
            result.append(
                {
                    "ticker": key[0],
                    "cohort": key[1],
                    "horizon_minutes": key[2],
                    "metric": metric,
                    "events": len(eligible),
                    "days": len(days),
                    "mean_day": original,
                    "median_event": float(np.median([getattr(r, metric) for r in eligible])),
                    "median_day": float(np.median(list(means.values()))),
                    "leave_one_day_out": leave_out,
                    "loo_min": min(leave_out.values()) if leave_out else None,
                    "loo_max": max(leave_out.values()) if leave_out else None,
                    "most_influential_day": max(
                        leave_out, key=lambda d: abs(leave_out[d] - original)
                    )
                    if leave_out
                    else None,
                    "isolated_events": sum(getattr(r, metric) is not None for r in isolated),
                    "isolated_days": len(iso),
                    "isolated_mean": float(np.mean(iso)) if iso else None,
                    "isolated_ci": bootstrap_mean(iso, settings),
                    "isolated_p": sign_p(np.array(iso) - null),
                }
            )
    adjust_fdr(result, "isolated_p", "isolated_q")
    return {
        "summaries": result,
        "isolation": (
            "No other observed original post in [publication-30min, response "
            "entry+60min]; stricter than overlapping asset-labelled windows only."
        ),
        "limitation": (
            "Leave-one-day-out range is sensitivity, not a confidence interval. "
            "Sparse isolated samples do not prove absence of an effect."
        ),
    }


def run_validation(
    study, market, posts_path, project_config, minute_config, validation_config, output
):
    from musk_sentiment.config import load_config
    from musk_sentiment.data.corpus import read_posts

    if (output / "manifest.json").exists():
        raise ValueError("Completed validation exists; select a separate output")
    frozen = json.loads((study / "manifest.json").read_text())
    if any(
        digest(Path(path).read_bytes()) != value for path, value in frozen["input_sha256"].items()
    ):
        raise ValueError("Frozen minute-study inputs changed")
    if any(
        digest((market / ticker / "manifest.json").read_bytes()) != value
        for ticker, value in frozen["market_manifest_sha256"].items()
    ):
        raise ValueError("Frozen minute-market manifests changed")
    settings = tomllib.loads(validation_config.read_text())["validation"]
    if settings["pre_minutes"] != 30 or settings["post_minutes"] != 60:
        raise ValueError("Current profile bins require the declared -30/+60-minute window")
    minute = tomllib.loads(minute_config.read_text())["minute"]
    project = load_config(project_config)
    assets = project["assets"]
    settings["control_start"] = project["research"]["start"]
    benchmarks = {a.ticker: a.benchmark for a in assets}
    events = [
        MinuteEvent.model_validate(r) for r in json.loads((study / "events.json").read_text())
    ]
    assignments = json.loads((study / "assignments.json").read_text())
    posts = read_posts(posts_path)
    store = MinuteStore(market)
    clock = SessionClock(minute["market_start"], minute["market_end"])
    old_hashes = {
        str(p): digest(p.read_bytes())
        for root in [study, Path("results/study_v7")]
        for p in root.rglob("*")
        if p.is_file()
    }
    print("Building balanced event-time profiles", flush=True)
    write_json(output / "event_profiles.json", event_profiles(assignments, store, clock, settings))
    print("Matching historical non-post controls", flush=True)
    write_json(
        output / "matched_placebos.json",
        matched_placebos(events, posts, store, clock, benchmarks, settings),
    )
    print("Checking influence and isolated posts", flush=True)
    write_json(output / "influence.json", influence_checks(events, posts, settings))
    if any(digest(Path(path).read_bytes()) != value for path, value in old_hashes.items()):
        raise ValueError("An earlier result changed during validation")
    manifest = {
        "settings": settings,
        "synthetic": False,
        "input_sha256": {
            str(p): digest(p.read_bytes())
            for p in [
                study / "events.json",
                study / "assignments.json",
                posts_path,
                project_config,
                minute_config,
                validation_config,
            ]
        },
        "source_sha256": digest(Path(__file__).read_bytes()),
        "previous_results_preserved": old_hashes,
        "limitations": [
            "Exploratory validation after inspecting earlier results",
            "No new test period or NLP revision",
            "Observed original corpus is not guaranteed complete",
            "Missing windows remain excluded; complete-case selection can bias samples",
            "Matched controls do not remove unobserved confounding",
        ],
    }
    write_json(output / "manifest.json", manifest)
    return {"output": str(output), "previous_files_unchanged": len(old_hashes)}
