"""Calendar-aware multi-asset event construction with explicit rejection accounting."""

from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import timedelta

import numpy as np

from musk_sentiment.data.alpaca import session_grid
from musk_sentiment.schemas import StudyRow


def build_study(posts, sentiments, markets, assets, interval, horizons, estimation=120, minimum=60):
    """No filling missing endpoints; market-model estimation ends before publication."""
    if not horizons or any(h < 1 for h in horizons) or minimum < 3 or estimation < minimum:
        raise ValueError("Invalid horizons or estimation window")
    pred = {r.output.post_id: r for r in sentiments}
    if len(pred) != len(sentiments) or set(pred) != {p.post_id for p in posts}:
        raise ValueError("Require exactly one NLP output per corpus post, with exact string IDs")
    versions = {(r.model, r.prompt_version) for r in sentiments}
    if len(versions) != 1:
        raise ValueError("Do not mix models or prompt versions within a study run")
    allowed = {a.ticker for a in assets}
    if any(s.ticker not in allowed for r in sentiments for s in r.output.assets):
        raise ValueError("Unconfigured NLP ticker")
    grids, maps = {}, {}
    for asset in assets:
        bars = sorted(markets.get(asset.ticker, []), key=lambda b: b.bar_start)
        if not bars:
            continue
        if any(b.ticker != asset.ticker or b.interval != interval for b in bars):
            raise ValueError("Mismatched ticker or interval in market input")
        if len({b.bar_start for b in bars}) != len(bars):
            raise ValueError("Duplicate market starts")
        if len({(b.source, b.adjusted) for b in bars}) != 1:
            raise ValueError("Mixed market sources/adjustments")
        start = bars[0].bar_start.date().isoformat()
        end = (bars[-1].bar_end.date() + timedelta(days=1)).isoformat()
        grid = session_grid(asset, start, end, interval)
        expected = dict(grid)
        if any(expected.get(b.bar_start) != b.bar_end for b in bars):
            raise ValueError("Bars not on canonical session grid; reaggregate at regular open")
        grids[asset.ticker] = grid
        maps[asset.ticker] = {b.bar_start: b for b in bars}
    asset_map = {a.ticker: a for a in assets}
    mentions = Counter()
    topic_mentions = Counter()
    rows = []
    rejected = []
    for post in sorted(posts, key=lambda p: (p.created_at, p.post_id)):
        nlp = pred[post.post_id]
        if nlp.synthetic != post.synthetic:
            raise ValueError("Mixed empirical/synthetic post and NLP")
        for signal in nlp.output.assets:
            ticker = signal.ticker
            asset = asset_map[ticker]
            mentions[ticker] += 1
            topic_indices = {}
            for topic in sorted(set(nlp.output.topics)):
                topic_mentions[(ticker, topic)] += 1
                topic_indices[topic] = topic_mentions[(ticker, topic)]
            for horizon in horizons:
                try:
                    if ticker not in maps:
                        raise ValueError("Missing asset market data")
                    grid = grids[ticker]
                    own = maps[ticker]
                    starts = [t[0] for t in grid]
                    ends = [t[1] for t in grid]
                    # First bar closing strictly after publication; preceding close is observable.
                    event_i = bisect_right(ends, post.created_at)
                    entry_i = bisect_left(starts, post.created_at)
                    end_i = event_i + horizon - 1
                    target_i = entry_i + horizon - 1
                    if event_i < 2 or max(end_i, target_i) >= len(grid):
                        raise ValueError("Insufficient baseline or outcome coverage")
                    needed = range(event_i - 2, max(end_i, target_i) + 1)
                    if any(starts[i] not in own for i in needed):
                        raise ValueError("Missing required event/prediction bar; no forward fill")
                    baseline = own[starts[event_i - 1]]
                    outcome = own[starts[end_i]]
                    entry = own[starts[entry_i]]
                    target = own[starts[target_i]]
                    if any(own[starts[i]].synthetic != post.synthetic for i in needed):
                        raise ValueError("Mixed empirical/synthetic prices")
                    ar = np.array(
                        [
                            own[starts[i]].close / own[starts[i - 1]].close - 1
                            for i in range(event_i, end_i + 1)
                        ]
                    )
                    benchmark_return = benchmark_car = market_car = alpha = beta = None
                    n = 0
                    benchmark = maps.get(asset.benchmark, {})
                    if asset.benchmark != ticker:
                        matching = all(
                            starts[i] in benchmark
                            and benchmark[starts[i]].bar_end == ends[i]
                            and benchmark[starts[i]].synthetic == post.synthetic
                            for i in range(event_i - 1, end_i + 1)
                        )
                        if not matching:
                            raise ValueError("Missing aligned benchmark endpoints")
                        br = np.array(
                            [
                                benchmark[starts[i]].close / benchmark[starts[i - 1]].close - 1
                                for i in range(event_i, end_i + 1)
                            ]
                        )
                        benchmark_return = (
                            benchmark[starts[end_i]].close / benchmark[starts[event_i - 1]].close
                            - 1
                        )
                        benchmark_car = float(np.sum(ar - br))
                        pairs = []
                        for i in range(max(1, event_i - estimation), event_i):
                            if all(
                                starts[j] in own
                                and starts[j] in benchmark
                                and benchmark[starts[j]].bar_end == ends[j]
                                for j in [i - 1, i]
                            ):
                                pairs.append(
                                    (
                                        benchmark[starts[i]].close / benchmark[starts[i - 1]].close
                                        - 1,
                                        own[starts[i]].close / own[starts[i - 1]].close - 1,
                                    )
                                )
                        n = len(pairs)
                        if n >= minimum:
                            x, y = np.array(pairs).T
                            if np.var(x) > 1e-16:
                                alpha, beta = map(
                                    float,
                                    np.linalg.lstsq(
                                        np.column_stack([np.ones(n), x]), y, rcond=None
                                    )[0],
                                )
                                market_car = float(np.sum(ar - alpha - beta * br))
                    history = []
                    for i in range(max(1, event_i - 20), event_i):
                        if starts[i] in own and starts[i - 1] in own:
                            history.append(own[starts[i]].close / own[starts[i - 1]].close - 1)
                    features = {
                        "lagged_return": baseline.close / own[starts[event_i - 2]].close - 1,
                        "volatility": float(np.std(history)) if history else 0.0,
                        "sentiment_score": signal.sentiment_score,
                        "first_mention": float(mentions[ticker] == 1),
                    }
                    rows.append(
                        StudyRow(
                            event_id=f"{post.post_id}:{ticker}:{interval}:{horizon}",
                            post_id=post.post_id,
                            ticker=ticker,
                            asset_class=asset.asset_class,
                            interval=interval,
                            horizon_bars=horizon,
                            posted_at=post.created_at,
                            baseline_at=baseline.bar_end,
                            outcome_at=outcome.bar_end,
                            entry_at=entry.bar_start,
                            label_end=target.bar_end,
                            mention_index=mentions[ticker],
                            topic_mention_indices=topic_indices,
                            topics=nlp.output.topics,
                            sentiment_score=signal.sentiment_score,
                            raw_return=outcome.close / baseline.close - 1,
                            benchmark_return=benchmark_return,
                            benchmark_car=benchmark_car,
                            market_model_car=market_car,
                            estimation_n=n,
                            alpha=alpha,
                            beta=beta,
                            predictive_return=target.close / entry.open - 1,
                            features=features,
                            synthetic=post.synthetic,
                        )
                    )
                except ValueError as exc:
                    rejected.append(
                        {
                            "post_id": post.post_id,
                            "ticker": ticker,
                            "interval": interval,
                            "horizon": horizon,
                            "reason": str(exc),
                        }
                    )
    return rows, rejected


def cluster_ids(rows):
    """Global overlapping explanatory/predictive windows form indivisible time clusters."""
    mapping = {}
    number = 0
    end = None
    for row in sorted(rows, key=lambda r: (r.baseline_at, r.event_id)):
        if end is None or row.baseline_at > end:
            number += 1
        end = max(end or row.label_end, row.label_end, row.outcome_at)
        mapping[row.event_id] = number
    return mapping


def describe_study(rows, seed=3544, repetitions=1000):
    """Cluster bootstrap intervals are exploratory, with small-cluster suppression."""
    rng = np.random.default_rng(seed)
    groups = defaultdict(list)
    for row in rows:
        direction = (
            "bullish"
            if row.sentiment_score > 0
            else "bearish"
            if row.sentiment_score < 0
            else "neutral"
        )
        for dimension, value in [
            ("asset", row.ticker),
            ("asset_class", row.asset_class),
            ("year", str(row.posted_at.year)),
            ("mention", "first" if row.mention_index == 1 else "subsequent"),
            ("sentiment", direction),
        ]:
            groups[(row.interval, row.horizon_bars, dimension, value)].append(row)
        for topic, ordinal in row.topic_mention_indices.items():
            groups[
                (
                    row.interval,
                    row.horizon_bars,
                    "topic_mention",
                    topic + (":first" if ordinal == 1 else ":subsequent"),
                )
            ].append(row)
    result = []
    for (interval, horizon, dimension, value), group in sorted(groups.items()):
        clusters = cluster_ids(group)
        for metric in ["raw_return", "benchmark_car", "market_model_car"]:
            eligible = [r for r in group if getattr(r, metric) is not None]
            if not eligible:
                continue
            blocks = defaultdict(list)
            for r in eligible:
                blocks[clusters[r.event_id]].append(getattr(r, metric))
            means = np.array([np.mean(v) for v in blocks.values()])
            ci = None
            p_value = None
            if len(means) >= 5:
                samples = np.array(
                    [
                        np.mean(rng.choice(means, len(means), replace=True))
                        for _ in range(repetitions)
                    ]
                )
                ci = np.quantile(samples, [0.025, 0.975]).tolist()
                null = [
                    abs(np.mean(means * rng.choice([-1, 1], len(means))))
                    for _ in range(repetitions)
                ]
                p_value = (1 + sum(v >= abs(np.mean(means)) for v in null)) / (repetitions + 1)
            result.append(
                {
                    "interval": interval,
                    "horizon": horizon,
                    "dimension": dimension,
                    "group": value,
                    "metric": metric,
                    "events": len(eligible),
                    "synthetic": any(r.synthetic for r in eligible),
                    "clusters": len(means),
                    "event_mean": float(np.mean([getattr(r, metric) for r in eligible])),
                    "equal_cluster_mean": float(np.mean(means)),
                    "cluster_bootstrap_95ci": ci,
                    "cluster_sign_flip_p": p_value,
                    "p_assumptions": "Independent clusters and symmetric cluster means under null",
                    "inference": "exploratory; intervals unadjusted for multiple comparisons",
                }
            )
    tested = sorted(
        (r for r in result if r["cluster_sign_flip_p"] is not None),
        key=lambda r: r["cluster_sign_flip_p"],
    )
    adjusted = 1.0
    for rank in range(len(tested), 0, -1):
        row = tested[rank - 1]
        adjusted = min(adjusted, row["cluster_sign_flip_p"] * len(tested) / rank)
        row["bh_fdr_q"] = adjusted
    return result
