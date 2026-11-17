"""Predeclared minute event study with distinct sessions and past-only activity references."""

import json
import math
import tomllib
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import UTC, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import numpy as np

from musk_sentiment.config import load_config
from musk_sentiment.data.corpus import read_posts
from musk_sentiment.nlp.pipeline import build_user_prompt
from musk_sentiment.schemas import MinuteBar, MinuteEvent, NLPRecord
from musk_sentiment.utils.io import digest, save_records, write_json

NY = ZoneInfo("America/New_York")
MINUTE = timedelta(minutes=1)


def ceil_minute(at):
    floor = at.replace(second=0, microsecond=0)
    return floor if at == floor else floor + MINUTE


class SessionClock:
    """DST-aware regular calendar; extended 04:00–20:00 local on session dates only."""

    def __init__(self, start, end):
        cal = xcals.get_calendar("XNYS", start=start, end=end)
        self.sessions = {
            cal.session_open(day).tz_convert(NY).date(): (
                cal.session_open(day).to_pydatetime(),
                cal.session_close(day).to_pydatetime(),
            )
            for day in cal.sessions
        }
        self.days = sorted(self.sessions)
        self.opens = [self.sessions[d][0] for d in self.days]
        self.closes = [self.sessions[d][1] for d in self.days]

    def classify(self, at, crypto=False):
        if crypto:
            return "crypto_24h", ceil_minute(at), None
        local = at.astimezone(NY)
        bounds = self.sessions.get(local.date())
        if bounds:
            opening, closing = bounds
            if opening <= at < closing:
                return "regular", ceil_minute(at), closing
            extended_open = datetime.combine(local.date(), time(4), NY).astimezone(UTC)
            extended_close = datetime.combine(local.date(), time(20), NY).astimezone(UTC)
            if extended_open <= at < opening:
                return "extended", ceil_minute(at), opening
            if closing <= at < extended_close:
                return "extended", ceil_minute(at), extended_close
        index = bisect_right(self.opens, at)
        if index == len(self.opens):
            raise ValueError("Next opening outside collected calendar")
        return "next_opening", self.opens[index], self.closes[index]

    def previous_close(self, at):
        index = bisect_right(self.closes, at) - 1
        if index < 0:
            raise ValueError("No prior regular close")
        return self.closes[index]

    def references(self, entry, cohort, count):
        if cohort == "crypto_24h":
            return [entry - timedelta(days=i) for i in range(1, count + 1)]
        local = entry.astimezone(NY)
        index = bisect_left(self.days, local.date())
        days = self.days[max(0, index - count) : index]
        if cohort == "next_opening":
            return [self.sessions[d][0] for d in days]
        return [
            datetime.combine(d, local.time().replace(tzinfo=None), NY).astimezone(UTC) for d in days
        ]

    def same_session_window(self, entry, end, cohort):
        if cohort == "crypto_24h":
            return True
        actual, _, boundary = self.classify(entry)
        expected = "regular" if cohort == "next_opening" else cohort
        return actual == expected and end <= boundary


class MinuteStore:
    """Lazy, hash-checked daily files; absent bars are never synthesized."""

    def __init__(self, root):
        self.root = root
        self.day = lru_cache(maxsize=128)(self._day)
        self.manifests = {}
        self.indices = {}
        for p in root.glob("*/manifest.json"):
            report = json.loads(p.read_text())
            if report["interval"] != "1min" or report["synthetic"]:
                raise ValueError("Require empirical one-minute sources")
            ticker = report["ticker"]
            self.manifests[ticker] = report
            self.indices[ticker] = {Path(x["path"]).stem: x for x in report["daily_files"]}

    def _day(self, ticker, day):
        info = self.indices.get(ticker, {}).get(day)
        if info is None:
            return {}
        path = Path(info["path"])
        payload = path.read_bytes()
        if digest(payload) != info["sha256"]:
            raise ValueError(f"Minute file hash mismatch: {path}")
        rows = [MinuteBar.model_validate(r) for r in json.loads(payload)]
        if len({b.t for b in rows}) != len(rows):
            raise ValueError("Duplicate minute timestamps")
        return {b.t: b for b in rows}

    def bar(self, ticker, at):
        return self.day(ticker, at.date().isoformat()).get(at)

    def window(self, ticker, entry, minutes):
        bars = [self.bar(ticker, entry + i * MINUTE) for i in range(minutes)]
        if any(b is None for b in bars):
            raise ValueError("Missing required one-minute bar; no filling")
        return bars


def measurements(bars):
    """Open-to-close return; unannualized realized volatility includes inter-minute changes."""
    previous = np.array([bars[0].o] + [b.c for b in bars[:-1]])
    changes = np.log(np.array([b.c for b in bars]) / previous)
    return {
        "forward_return": bars[-1].c / bars[0].o - 1,
        "volume": sum(b.v for b in bars),
        "trade_count": sum(b.n for b in bars),
        "realized_volatility": float(np.sqrt(np.sum(changes**2))),
    }


def relative_activity(store, clock, ticker, entry, posted_at, cohort, horizon, settings):
    references = []
    starts = clock.references(entry, cohort, settings["baseline_sessions"])
    for start in starts:
        end = start + horizon * MINUTE
        if end > posted_at or not clock.same_session_window(start, end, cohort):
            continue
        try:
            references.append(measurements(store.window(ticker, start, horizon)))
        except ValueError as exc:
            if "Missing required" not in str(exc):
                raise
    result = {"reference_windows": len(references)}
    for field, name in [
        ("volume", "volume"),
        ("trade_count", "trade_count"),
        ("realized_volatility", "volatility"),
    ]:
        result["reference_" + name] = (
            float(np.median([r[field] for r in references]))
            if len(references) >= settings["minimum_baseline_windows"]
            else None
        )
    return result


def build_minute_events(posts, nlp, assets, store, settings, prior_mentions=None):
    clock = SessionClock(settings["market_start"], settings["market_end"])
    asset_map = {a.ticker: a for a in assets}
    predictions = {r.output.post_id: r for r in nlp}
    if len(predictions) != len(nlp) or set(predictions) != {p.post_id for p in posts}:
        raise ValueError("Require exactly one NLP result per post")
    versions = {(r.model, r.prompt_version) for r in nlp}
    if len(versions) != 1:
        raise ValueError("Mixed NLP versions")
    events, rejected, assignments = [], [], []
    mentions = Counter(prior_mentions or {})
    for post in sorted(posts, key=lambda p: (p.created_at, p.post_id)):
        result = predictions[post.post_id]
        if result.synthetic or post.synthetic:
            raise ValueError("Synthetic inputs forbidden")
        for signal in result.output.assets:
            asset = asset_map[signal.ticker]
            ticker = asset.ticker
            mentions[ticker] += 1
            cohort, entry, boundary = clock.classify(post.created_at, asset.asset_class == "crypto")
            assignments.append(
                {
                    "post_id": post.post_id,
                    "ticker": ticker,
                    "cohort": cohort,
                    "posted_at": post.created_at.isoformat(),
                    "entry_at": entry.isoformat(),
                }
            )
            baseline_end = (
                clock.previous_close(post.created_at)
                if cohort == "next_opening"
                else post.created_at.replace(second=0, microsecond=0)
            )
            for horizon in settings["horizons_minutes"]:
                try:
                    end = entry + horizon * MINUTE
                    if boundary and end > boundary:
                        raise ValueError("Window crosses session boundary")
                    baseline = store.bar(ticker, baseline_end - MINUTE)
                    if baseline is None:
                        raise ValueError("Missing pre-publication baseline minute")
                    bars = store.window(ticker, entry, horizon)
                    outcome = measurements(bars)
                    refs = relative_activity(
                        store, clock, ticker, entry, post.created_at, cohort, horizon, settings
                    )
                    for measured, name in [
                        ("volume", "volume"),
                        ("trade_count", "trade_count"),
                        ("realized_volatility", "volatility"),
                    ]:
                        reference = refs["reference_" + name]
                        refs["relative_" + name] = (
                            outcome[measured] / reference
                            if reference is not None and reference > 0
                            else None
                        )
                    bench_return = None
                    if asset.benchmark != ticker:
                        benchmark = store.window(asset.benchmark, entry, horizon)
                        bench_return = measurements(benchmark)["forward_return"]
                    features = None
                    try:
                        pre = measurements(store.window(ticker, baseline_end - 5 * MINUTE, 5))
                        features = {
                            "lagged_return": pre["forward_return"],
                            "volatility": pre["realized_volatility"],
                            "log_volume": math.log1p(pre["volume"]),
                            "log_trades": math.log1p(pre["trade_count"]),
                            "lag_age_minutes": (post.created_at - baseline_end).total_seconds()
                            / 60,
                        }
                    except ValueError as exc:
                        if "Missing required" not in str(exc):
                            raise
                    events.append(
                        MinuteEvent(
                            event_id=f"{post.post_id}:{ticker}:{cohort}:{horizon}m",
                            post_id=post.post_id,
                            ticker=ticker,
                            cohort=cohort,
                            horizon_minutes=horizon,
                            posted_at=post.created_at,
                            entry_at=entry,
                            end_at=end,
                            baseline_at=baseline_end,
                            entry_delay_seconds=(entry - post.created_at).total_seconds(),
                            sentiment_score=signal.sentiment_score,
                            topics=result.output.topics,
                            mention_index=mentions[ticker],
                            **outcome,
                            **refs,
                            baseline_to_end_return=bars[-1].c / baseline.c - 1,
                            opening_gap_return=bars[0].o / baseline.c - 1
                            if cohort == "next_opening"
                            else None,
                            benchmark_return=bench_return,
                            benchmark_adjusted_return=outcome["forward_return"] - bench_return
                            if bench_return is not None
                            else None,
                            features=features,
                            features_end_at=baseline_end if features else None,
                        )
                    )
                except ValueError as exc:
                    if not any(
                        x in str(exc)
                        for x in ["Missing required", "Missing pre-publication", "Window crosses"]
                    ):
                        raise
                    rejected.append(
                        {
                            "post_id": post.post_id,
                            "ticker": ticker,
                            "cohort": cohort,
                            "horizon_minutes": horizon,
                            "reason": str(exc),
                        }
                    )
    return events, rejected, assignments


def clusters(rows):
    """Join overlapping response intervals; identical next-opening outcomes share a cluster."""
    result, number, end = {}, 0, None
    for row in sorted(rows, key=lambda r: (r.entry_at, r.event_id)):
        if end is None or row.entry_at >= end:
            number += 1
        end = max(end or row.end_at, row.end_at)
        result[row.event_id] = number
    return result


def adjust_fdr(rows, p_key, q_key):
    ranked = sorted((r for r in rows if r.get(p_key) is not None), key=lambda r: r[p_key])
    last = 1.0
    for i in range(len(ranked), 0, -1):
        row = ranked[i - 1]
        last = min(last, row[p_key] * len(ranked) / i)
        row[q_key] = last


def describe_minutes(events, settings, cluster_unit="overlap"):
    """Exploratory cluster summaries and cluster-level sentiment correlations; BH within family."""
    from scipy.stats import binomtest, spearmanr

    groups = defaultdict(list)
    for row in events:
        groups[(row.ticker, row.cohort, row.horizon_minutes)].append(row)
    summaries, relationships = [], []
    rng = np.random.default_rng(settings["seed"])
    metrics = [
        "forward_return",
        "benchmark_adjusted_return",
        "relative_volume",
        "relative_trade_count",
        "relative_volatility",
    ]
    for key, rows in sorted(groups.items()):
        if cluster_unit == "overlap":
            mapping = clusters(rows)
        elif cluster_unit == "day":
            mapping = {
                r.event_id: r.entry_at.astimezone(UTC if r.cohort == "crypto_24h" else NY).date()
                for r in rows
            }
        else:
            raise ValueError("Unknown minute clustering unit")
        for metric in metrics:
            eligible = [r for r in rows if getattr(r, metric) is not None]
            if not eligible:
                continue
            blocks = defaultdict(list)
            for row in eligible:
                blocks[mapping[row.event_id]].append(row)
            values = np.array(
                [np.mean([getattr(r, metric) for r in block]) for block in blocks.values()]
            )
            null = 1.0 if metric.startswith("relative_") else 0.0
            ci, p = None, None
            if len(values) >= 5:
                boot = rng.choice(
                    values, (settings["bootstrap_repetitions"], len(values)), replace=True
                ).mean(axis=1)
                ci = np.quantile(boot, [0.025, 0.975]).tolist()
                centered = values - null
                nonzero = centered[centered != 0]
                if len(nonzero):
                    p = float(binomtest(int(sum(nonzero > 0)), len(nonzero), 0.5).pvalue)
            summaries.append(
                {
                    "ticker": key[0],
                    "cohort": key[1],
                    "horizon_minutes": key[2],
                    "metric": metric,
                    "events": len(eligible),
                    "clusters": len(values),
                    "event_mean": float(np.mean([getattr(r, metric) for r in eligible])),
                    "equal_cluster_mean": float(values.mean()),
                    "cluster_bootstrap_95ci": ci,
                    "sign_test_p": p,
                    "null_cluster_median": null,
                }
            )
            for kind in ["signed", "absolute"]:
                scores = np.array(
                    [
                        np.mean(
                            [
                                r.sentiment_score if kind == "signed" else abs(r.sentiment_score)
                                for r in block
                            ]
                        )
                        for block in blocks.values()
                    ]
                )
                rho, prob = None, None
                if len(values) >= 5 and len(set(scores)) > 1 and len(set(values)) > 1:
                    rho, prob = map(float, spearmanr(scores, values))
                relationships.append(
                    {
                        "ticker": key[0],
                        "cohort": key[1],
                        "horizon_minutes": key[2],
                        "metric": metric,
                        "sentiment": kind,
                        "clusters": len(values),
                        "spearman_rho": rho,
                        "p_value": prob,
                    }
                )
    adjust_fdr(summaries, "sign_test_p", "bh_fdr_q")
    adjust_fdr(relationships, "p_value", "bh_fdr_q")
    return {
        "cluster_unit": cluster_unit,
        "summaries": summaries,
        "sentiment_relationships": relationships,
        "limitations": [
            "Association, not causation",
            "Unadjusted bootstrap intervals; BH separately over summary and correlation tests",
            "Sign tests concern cluster median, bootstrap intervals concern equal-cluster mean",
            "Independent clusters assumed; market-wide confounding remains",
            "No realized future activity enters prediction features",
        ],
    }


def run_minutes(posts_path, nlp_path, market_dir, config_path, minute_config, output, old_results):
    from musk_sentiment.models.minute import evaluate_minute_models

    if (output / "manifest.json").exists():
        raise ValueError("Minute run already exists; choose a new output directory")
    config = load_config(config_path)
    settings = tomllib.loads(minute_config.read_text())["minute"]
    if settings["extended_open"] != "04:00" or settings["extended_close"] != "20:00":
        raise ValueError("This version supports only the documented 04:00–20:00 extended sessions")
    posts = read_posts(posts_path)
    if any(
        not config["research"]["start"]
        <= p.created_at.date().isoformat()
        < config["research"]["end"]
        for p in posts
    ):
        raise ValueError("Posts outside approved research scope")
    nlp = [NLPRecord.model_validate(r) for r in json.loads(nlp_path.read_text())]
    by_id = {p.post_id: p for p in posts}
    for r in nlp:
        if r.output.post_id not in by_id or r.input_sha256 != digest(
            build_user_prompt(by_id[r.output.post_id], config["assets"]).encode()
        ):
            raise ValueError("NLP corpus/universe fingerprint mismatch")
    store = MinuteStore(market_dir)
    events, rejections, assignments = build_minute_events(
        posts, nlp, config["assets"], store, settings
    )
    save_records(output / "events.json", events)
    write_json(output / "rejections.json", rejections)
    write_json(output / "assignments.json", assignments)
    write_json(output / "descriptive.json", describe_minutes(events, settings))
    write_json(output / "day_cluster_sensitivity.json", describe_minutes(events, settings, "day"))
    common_ids = {}
    for row in events:
        common_ids.setdefault((row.ticker, row.cohort, row.post_id), set()).add(row.horizon_minutes)
    common = [
        r
        for r in events
        if common_ids[(r.ticker, r.cohort, r.post_id)] == set(settings["horizons_minutes"])
    ]
    write_json(output / "common_horizon_sensitivity.json", describe_minutes(common, settings))
    counts = Counter((r.ticker, r.cohort, r.horizon_minutes) for r in events)
    write_json(
        output / "coverage.json",
        {
            "accepted": [
                {"ticker": t, "cohort": c, "horizon_minutes": h, "events": n}
                for (t, c, h), n in sorted(counts.items())
            ],
            "rejection_reasons": dict(Counter(r["reason"] for r in rejections)),
            "activity_reference_missing": {
                field: sum(getattr(r, field) is None for r in events)
                for field in ["relative_volume", "relative_trade_count", "relative_volatility"]
            },
        },
    )
    write_json(output / "models.json", evaluate_minute_models(events, settings))
    old = json.loads((old_results / "events.json").read_text())
    comparison = []
    for (ticker, cohort, horizon), count in sorted(counts.items()):
        new_rows = [
            r
            for r in events
            if (r.ticker, r.cohort, r.horizon_minutes) == (ticker, cohort, horizon)
        ]
        ids = {r.post_id for r in new_rows}
        for interval in ["1h", "1d"]:
            baseline = [
                r
                for r in old
                if r["ticker"] == ticker
                and r["interval"] == interval
                and r["horizon_bars"] == 1
                and r["post_id"] in ids
            ]
            comparison.append(
                {
                    "ticker": ticker,
                    "cohort": cohort,
                    "new_horizon_minutes": horizon,
                    "new_events": count,
                    "new_mean_forward_return": float(np.mean([r.forward_return for r in new_rows])),
                    "old_interval": interval,
                    "old_matched_events": len(baseline),
                    "old_mean_predictive_return": float(
                        np.mean([r["predictive_return"] for r in baseline])
                    )
                    if baseline
                    else None,
                    "note": (
                        "Matched post IDs; different horizons/entry definitions, "
                        "not an accuracy-improvement test"
                    ),
                }
            )
    write_json(output / "old_comparison.json", comparison)
    manifest = {
        "synthetic": False,
        "events": len(events),
        "rejected": len(rejections),
        "assigned_post_assets": len(assignments),
        "settings": settings,
        "input_sha256": {
            str(p): digest(p.read_bytes())
            for p in [posts_path, nlp_path, config_path, minute_config, old_results / "events.json"]
        },
        "implementation_sha256": {
            str(path): digest(path.read_bytes())
            for path in [
                Path(__file__),
                Path(__file__).parents[1] / "models/minute.py",
                Path(__file__).parents[1] / "data/minute.py",
                Path(__file__).parents[1] / "schemas.py",
            ]
        },
        "market_manifest_sha256": {
            t: digest((market_dir / t / "manifest.json").read_bytes()) for t in store.manifests
        },
        "nlp_versions": sorted({r.model + "/" + r.prompt_version for r in nlp}),
        "status": "Retrospective exploratory minute study; session-separated and no gap filling",
    }
    write_json(output / "manifest.json", manifest)
    return manifest
