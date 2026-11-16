"""Reproducible blinded samples and exact-ID, multi-asset annotation evaluation."""

import csv
import json
import random
from collections import defaultdict

from musk_sentiment.schemas import AssetSentiment, NLPRecord
from musk_sentiment.utils.io import digest, write_json

FIELDS = [
    "post_id",
    "text",
    "created_at",
    "split",
    "stratum",
    "ticker",
    "annotator_id",
    "market_relevant",
    "sentiment",
    "sentiment_score",
    "topic",
    "impact_horizon",
    "ambiguous",
    "notes",
]


def sample_annotations(posts, assets, output, per_quarter=20, seed=3544):
    """Adapt Cyrus's random+keyword design, preserving IDs and balancing eight quarters."""
    if output.exists():
        raise ValueError("Annotation sample already exists; use a new output path")
    rng = random.Random(seed)
    groups = defaultdict(list)
    aliases = [s.lower() for a in assets for s in [a.ticker, *a.aliases]]
    for p in posts:
        groups[(p.created_at.year, (p.created_at.month - 1) // 3)].append(p)
    rows = []
    for _quarter, pool in sorted(groups.items()):
        pool = sorted(pool, key=lambda p: p.post_id)
        random_sample = rng.sample(pool, min(per_quarter // 2, len(pool)))
        used = {p.post_id for p in random_sample}
        keywords = [
            p for p in pool if p.post_id not in used and any(a in p.text.lower() for a in aliases)
        ]
        enriched = rng.sample(keywords, min(per_quarter - len(random_sample), len(keywords)))
        for stratum, sample in [("random", random_sample), ("keyword", enriched)]:
            rng.shuffle(sample)
            for i, p in enumerate(sample):
                row = dict.fromkeys(FIELDS, "")
                row.update(
                    post_id=p.post_id,
                    text=p.text,
                    created_at=p.created_at.isoformat(),
                    split="dev" if i < max(1, len(sample) // 3) else "test",
                    stratum=stratum,
                )
                rows.append(row)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "seed": seed,
        "rows": len(rows),
        "quarters": len(groups),
        "sample_sha256": digest(output.read_bytes()),
        "warning": "Blinded human labels required; enriched sample is not population prevalence",
    }
    write_json(output.with_suffix(".manifest.json"), report)
    return report


def score_annotations(labels, predictions, split="test", reference_type="unspecified"):
    with labels.open(newline="", encoding="utf-8-sig") as stream:
        rows = [r for r in csv.DictReader(stream) if r.get("split") == split]
    if not rows:
        raise ValueError("No labels for requested split")
    gold = {}
    for r in rows:
        if not r["annotator_id"].strip() or r["market_relevant"].lower() not in {"true", "false"}:
            raise ValueError("Complete annotator/relevance labels required")
        relevant = r["market_relevant"].lower() == "true"
        entry = gold.setdefault(r["post_id"], {"relevant": relevant, "assets": {}})
        if relevant != entry["relevant"]:
            raise ValueError("Conflicting labels; adjudicate before scoring")
        if r["ticker"]:
            if not relevant or r["ticker"] in entry["assets"]:
                raise ValueError("Duplicate asset or asset on irrelevant post")
            asset = AssetSentiment(
                ticker=r["ticker"],
                sentiment=r["sentiment"],
                sentiment_score=float(r["sentiment_score"]),
                confidence=0,
            )
            entry["assets"][r["ticker"]] = asset.sentiment
    records = [NLPRecord.model_validate(v) for v in json.loads(predictions.read_text())]
    if any(r.synthetic for r in records):
        raise ValueError("Synthetic predictions cannot be scored as empirical labels")
    pred = {r.output.post_id: r.output for r in records}
    if len(pred) != len(records):
        raise ValueError("Duplicate prediction IDs")
    missing = sorted(set(gold) - set(pred))
    if missing:
        raise ValueError(f"Missing exact-ID predictions for {len(missing)} labels; no fuzzy repair")
    tp = fp = fn = tn = asset_exact = sent_ok = sent_n = 0
    for pid, g in gold.items():
        p = pred[pid]
        yes = g["relevant"]
        tp += int(yes and p.market_relevant)
        fn += int(yes and not p.market_relevant)
        fp += int(not yes and p.market_relevant)
        tn += int(not yes and not p.market_relevant)
        assets = {a.ticker: a.sentiment for a in p.assets}
        asset_exact += int(set(assets) == set(g["assets"]))
        for ticker, label in g["assets"].items():
            sent_n += 1
            sent_ok += int(assets.get(ticker) == label)
    return {
        "split": split,
        "posts": len(gold),
        "reference_type": reference_type,
        "reference_annotators": sorted({r["annotator_id"] for r in rows}),
        "interpretation": (
            "Agreement with supplied reference labels; "
            "independent human accuracy has not been established."
        ),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "relevance_accuracy": (tp + tn) / len(gold),
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "asset_set_accuracy": asset_exact / len(gold),
        "gold_asset_sentiment_accuracy": sent_ok / sent_n if sent_n else None,
        "gold_assets": sent_n,
        "synthetic": False,
    }
