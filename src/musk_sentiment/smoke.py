"""Entirely synthetic, deterministic integration workflow; no network calls."""

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from musk_sentiment.alignment.calendar import next_trading_time
from musk_sentiment.analysis.returns import benchmark_adjusted, simple_return
from musk_sentiment.config import load_config
from musk_sentiment.data.market import normalize_market
from musk_sentiment.data.posts import import_posts
from musk_sentiment.features.validation import purged_split
from musk_sentiment.nlp.pipeline import infer
from musk_sentiment.nlp.provider import SyntheticProvider
from musk_sentiment.schemas import EventReturn, FeatureRow, PostAssetEvent
from musk_sentiment.utils.io import save_records, snapshot, write_json


def run_smoke(fixture: Path, config: Path, output: Path) -> dict:
    assets = load_config(config)["assets"]
    posts, quality = import_posts(
        fixture, output / "processed", output / "raw", "synthetic-fixture-v1", synthetic=True
    )
    if not posts:
        raise ValueError("Smoke fixture produced no clean posts")
    provider = SyntheticProvider()
    sentiments = [infer(p, assets, provider, output / "nlp_cache") for p in posts]
    save_records(output / "processed" / "sentiments.json", sentiments)
    # Fixed prices are deliberately invented, visibly labelled, and never research data.
    asset = assets[0]
    frame = pd.DataFrame(
        {
            "Open": [100, 101, 102],
            "High": [102, 103, 104],
            "Low": [99, 100, 101],
            "Close": [101, 102, 103],
            "Volume": [10, 20, 30],
        },
        index=pd.to_datetime(["2024-07-03", "2024-07-05", "2024-07-08"]),
    )
    snapshot(output / "raw", frame.to_csv().encode(), ".synthetic-market.csv")
    bars, rejected = normalize_market(frame, asset, "1d", datetime(2024, 7, 10, tzinfo=UTC))
    bars = [
        bar.model_copy(update={"source": "synthetic-fixture-v1", "synthetic": True}) for bar in bars
    ]
    save_records(output / "processed" / "market_synthetic.json", bars)
    events, returns, features = [], [], []
    for ordinal, (post, sentiment) in enumerate(zip(posts, sentiments, strict=True), 1):
        event = PostAssetEvent(
            event_id=f"{post.post_id}:{asset.ticker}",
            post_id=post.post_id,
            ticker=asset.ticker,
            posted_at=post.created_at,
            prediction_at=post.created_at,
            mention_index=ordinal,
            first_observed_mention=ordinal == 1,
            sentiment_score=sentiment.output.assets[0].sentiment_score,
            synthetic=True,
        )
        # Wiring demonstration only: latest completed close before post, then next session close.
        baseline = max(
            (b for b in bars if b.bar_end <= event.prediction_at), key=lambda b: b.bar_end
        )
        trading_time = next_trading_time(post.created_at, asset.calendar)
        outcome = min((b for b in bars if b.bar_start >= trading_time), key=lambda b: b.bar_start)
        raw = simple_return(baseline.close, outcome.close)
        result = EventReturn(
            event_id=event.event_id,
            ticker=asset.ticker,
            prediction_at=event.prediction_at,
            baseline_at=baseline.bar_end,
            outcome_at=outcome.bar_end,
            interval="1d",
            horizon_bars=1,
            raw_return=raw,
            benchmark_return=0,
            abnormal_return=benchmark_adjusted(raw, 0),
            synthetic=True,
        )
        features.append(
            FeatureRow(
                event_id=event.event_id,
                ticker=asset.ticker,
                prediction_at=event.prediction_at,
                features_available_at=event.prediction_at,
                label_end=result.outcome_at,
                features={"sentiment_score": event.sentiment_score},
                target=result.raw_return,
                synthetic=True,
            )
        )
        events.append(event)
        returns.append(result)
    save_records(output / "final" / "events.json", events)
    save_records(output / "final" / "returns.json", returns)
    save_records(output / "final" / "features.json", features)
    train, test = purged_split(features, datetime(2024, 7, 6, tzinfo=UTC))
    summary = {
        "synthetic": True,
        "warning": "Wiring test only; no empirical predictions or findings",
        "clean_posts": len(posts),
        "sentiments": len(sentiments),
        "market_bars": len(bars),
        "market_rejections": rejected,
        "events": len(events),
        "returns": len(returns),
        "train_rows": len(train),
        "test_rows": len(test),
        "post_quality": quality["counts"],
    }
    write_json(output / "summary.json", summary)
    return summary
