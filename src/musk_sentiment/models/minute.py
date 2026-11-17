"""Fixed, purged chronological prediction of minute returns and activity outcomes."""

from collections import defaultdict
from datetime import UTC, datetime

import numpy as np

from musk_sentiment.analysis.minute import clusters
from musk_sentiment.models.research import metrics


def split_minute_rows(rows, cutoff):
    """No outcome spanning a boundary, or shared evaluation response cluster, enters training."""
    mapping = clusters(rows)
    test = [r for r in rows if r.posted_at >= cutoff]
    excluded = {mapping[r.event_id] for r in test}
    train = [r for r in rows if r.end_at < cutoff and mapping[r.event_id] not in excluded]
    return train, test


def evaluate_minute_models(events, settings, test_only=False):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.feature_extraction import DictVectorizer
    from sklearn.linear_model import LinearRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    groups = defaultdict(list)
    for r in events:
        groups[(r.ticker, r.cohort, r.horizon_minutes)].append(r)
    scores, skipped, predictions, improvements = [], [], [], []
    validation = datetime.fromisoformat(settings["validation_start"]).replace(tzinfo=UTC)
    final = datetime.fromisoformat(settings["test_start"]).replace(tzinfo=UTC)
    if validation >= final:
        raise ValueError("Validation must precede test")
    for key, group in sorted(groups.items()):
        for target in [
            "forward_return",
            "relative_volume",
            "relative_trade_count",
            "relative_volatility",
        ]:
            complete = [
                r for r in group if r.features is not None and getattr(r, target) is not None
            ]
            phases = (
                [("test", final)] if test_only else [("validation", validation), ("test", final)]
            )
            for phase, cutoff in phases:
                pool = complete if phase == "test" else [r for r in complete if r.end_at < final]
                train, test = split_minute_rows(pool, cutoff)
                base = {
                    "ticker": key[0],
                    "cohort": key[1],
                    "horizon_minutes": key[2],
                    "target": target,
                    "phase": phase,
                    "train_events": len(train),
                    "test_events": len(test),
                }
                if len(train) < 20 or len(test) < 5:
                    skipped.append(
                        {**base, "reason": "Require 20 training and 5 evaluation events"}
                    )
                    continue
                y = np.array([getattr(r, target) for r in train])
                truth = np.array([getattr(r, target) for r in test])
                estimates = {
                    "no_change": np.repeat(0.0 if target == "forward_return" else 1.0, len(test)),
                    "historical_mean": np.repeat(y.mean(), len(test)),
                }

                def features(row, augmented):
                    result = dict(row.features)
                    if augmented:
                        result.update(
                            sentiment_score=row.sentiment_score,
                            absolute_sentiment=abs(row.sentiment_score),
                            first_mention=float(row.mention_index == 1),
                        )
                        result.update({"topic:" + t: 1.0 for t in row.topics})
                    return result

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
                                random_state=settings["seed"],
                                n_jobs=1,
                            ),
                        ),
                    ]:
                        pipeline = make_pipeline(
                            DictVectorizer(sparse=False), StandardScaler(), model
                        )
                        pipeline.fit(x, y)
                        estimates[name + ("_nlp" if augmented else "_market")] = pipeline.predict(
                            xt
                        )
                for name, estimate in estimates.items():
                    measured = metrics(truth, estimate)
                    if target != "forward_return":
                        measured.pop("directional_accuracy")
                    scores.append({**base, "model": name, **measured})
                    for r, prediction in zip(test, estimate, strict=True):
                        predictions.append(
                            {
                                "event_id": r.event_id,
                                "target": target,
                                "phase": phase,
                                "model": name,
                                "actual": float(getattr(r, target)),
                                "predicted": float(prediction),
                            }
                        )
                mapping = clusters(test)
                for name in ["linear", "ridge", "tree"]:
                    delta = np.abs(truth - estimates[name + "_market"]) - np.abs(
                        truth - estimates[name + "_nlp"]
                    )
                    blocks = defaultdict(list)
                    for row, value in zip(test, delta, strict=True):
                        blocks[mapping[row.event_id]].append(value)
                    values = np.array([np.mean(x) for x in blocks.values()])
                    ci = None
                    if len(values) >= 5:
                        rng = np.random.default_rng(settings["seed"])
                        boot = rng.choice(
                            values, (settings["bootstrap_repetitions"], len(values)), replace=True
                        ).mean(axis=1)
                        ci = np.quantile(boot, [0.025, 0.975]).tolist()
                    improvements.append(
                        {
                            **base,
                            "model": name,
                            "clusters": len(values),
                            "mae_improvement": float(delta.mean()),
                            "equal_cluster_improvement": float(values.mean()),
                            "cluster_bootstrap_95ci": ci,
                        }
                    )
    return {
        "scores": scores,
        "nlp_improvements": improvements,
        "predictions": predictions,
        "skipped": skipped,
        "policy": (
            "Fixed models/settings; chronological validation/test; "
            "response overlap purged; pre-publication market features only"
        ),
        "caveats": [
            "Earlier results inspected; exploratory follow-up, not an untouched experiment",
            "Modern NLP may know historical outcomes",
            "Comparisons across horizons/cohorts differ in sample and target",
            "Activity regressions are unconstrained; negative forecasts are not clipped",
            "Model confidence intervals are exploratory and not multiplicity-adjusted",
        ],
    }
