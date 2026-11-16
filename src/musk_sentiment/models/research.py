"""Fixed chronological validation/test and training-only feature transformations."""

from collections import defaultdict

import numpy as np
import pandas as pd

from musk_sentiment.analysis.study import cluster_ids


def chronological_split(rows, cutoff):
    cutoff = pd.Timestamp(cutoff, tz="UTC").to_pydatetime()
    clusters = cluster_ids(rows)
    test = [r for r in rows if r.posted_at >= cutoff]
    test_clusters = {clusters[r.event_id] for r in test}
    train = [
        r
        for r in rows
        if max(r.label_end, r.outcome_at) < cutoff and clusters[r.event_id] not in test_clusters
    ]
    return train, test


def metrics(y, pred):
    y = np.asarray(y)
    pred = np.asarray(pred)
    return {
        "mae": float(np.mean(np.abs(y - pred))),
        "rmse": float(np.sqrt(np.mean((y - pred) ** 2))),
        "directional_accuracy": float(np.mean(np.sign(y) == np.sign(pred))),
    }


def evaluate_models(rows, validation_start, test_start, seed=3544):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if pd.Timestamp(validation_start) >= pd.Timestamp(test_start):
        raise ValueError("Validation must precede test")
    groups = defaultdict(list)
    for r in rows:
        groups[(r.ticker, r.interval, r.horizon_bars)].append(r)
    scores = []
    predictions = []
    skipped = []
    for key, group in sorted(groups.items()):
        for phase, cutoff in [("validation", validation_start), ("test", test_start)]:
            # Validation labels ending in test period must not inform model selection.
            pool = (
                group
                if phase == "test"
                else [
                    r
                    for r in group
                    if max(r.label_end, r.outcome_at) < pd.Timestamp(test_start, tz="UTC")
                ]
            )
            train, test = chronological_split(pool, cutoff)
            if len(train) < 20 or len(test) < 5:
                skipped.append(
                    {
                        "group": list(key),
                        "phase": phase,
                        "train": len(train),
                        "test": len(test),
                        "reason": "At least 20 training and 5 evaluation events required",
                    }
                )
                continue
            y = np.array([r.predictive_return for r in train])
            truth = np.array([r.predictive_return for r in test])
            estimates = {
                "zero": np.zeros(len(test)),
                "historical_mean": np.repeat(y.mean(), len(test)),
                "lagged_return": np.array(
                    [r.features["lagged_return"] * r.horizon_bars for r in test]
                ),
            }

            def features(row, nlp):
                out = {
                    k: v for k, v in row.features.items() if k in {"lagged_return", "volatility"}
                }
                if nlp:
                    out.update(
                        sentiment_score=row.sentiment_score,
                        first_mention=float(row.mention_index == 1),
                    )
                    out.update({"topic:" + t: 1.0 for t in row.topics})
                return out

            for augmented in [False, True]:
                x = [features(r, augmented) for r in train]
                xt = [features(r, augmented) for r in test]
                for name, model in [
                    ("linear", LinearRegression()),
                    ("ridge", Ridge(alpha=1.0)),
                    (
                        "tree",
                        RandomForestRegressor(
                            n_estimators=100,
                            max_depth=3,
                            min_samples_leaf=5,
                            random_state=seed,
                            n_jobs=1,
                        ),
                    ),
                ]:
                    pipeline = make_pipeline(DictVectorizer(sparse=False), StandardScaler(), model)
                    pipeline.fit(x, y)
                    estimates[name + ("_nlp" if augmented else "_market")] = pipeline.predict(xt)
            for name, estimate in estimates.items():
                scores.append(
                    {
                        "ticker": key[0],
                        "interval": key[1],
                        "horizon": key[2],
                        "phase": phase,
                        "model": name,
                        "train_events": len(train),
                        "test_events": len(test),
                        **metrics(truth, estimate),
                    }
                )
                for row, value in zip(test, estimate, strict=True):
                    predictions.append(
                        {
                            "event_id": row.event_id,
                            "phase": phase,
                            "model": name,
                            "actual": row.predictive_return,
                            "predicted": float(value),
                        }
                    )
            for name in ["linear", "ridge", "tree"]:
                # Paired errors on identical test events; report uncertainty by overlap cluster.
                cluster = cluster_ids(test)
                blocks = defaultdict(list)
                delta = np.abs(truth - estimates[name + "_market"]) - np.abs(
                    truth - estimates[name + "_nlp"]
                )
                for row, d in zip(test, delta, strict=True):
                    blocks[cluster[row.event_id]].append(d)
                means = np.array([np.mean(v) for v in blocks.values()])
                ci = None
                if len(means) >= 5:
                    rng = np.random.default_rng(seed)
                    boot = [
                        np.mean(rng.choice(means, len(means), replace=True)) for _ in range(1000)
                    ]
                    ci = np.quantile(boot, [0.025, 0.975]).tolist()
                scores.append(
                    {
                        "ticker": key[0],
                        "interval": key[1],
                        "horizon": key[2],
                        "phase": phase,
                        "model": name + "_nlp_improvement",
                        "mae_improvement": float(np.mean(delta)),
                        "equal_cluster_improvement": float(np.mean(means)),
                        "cluster_bootstrap_95ci": ci,
                        "clusters": len(means),
                    }
                )
    return {
        "synthetic": any(r.synthetic for r in rows),
        "scores": scores,
        "predictions": predictions,
        "skipped": skipped,
        "policy": "Fixed hyperparameters; validation and final test chronological, overlap purged",
        "target": "Next complete bar open to horizon close; before costs, not executable P&L",
    }
