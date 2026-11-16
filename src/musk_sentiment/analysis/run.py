"""Reproducible offline study orchestration; real and synthetic runs stay separate."""

import json
from pathlib import Path

from musk_sentiment.analysis.study import build_study, cluster_ids, describe_study
from musk_sentiment.config import load_config
from musk_sentiment.data.corpus import read_posts, select_window
from musk_sentiment.models.research import evaluate_models
from musk_sentiment.nlp.pipeline import build_user_prompt
from musk_sentiment.schemas import MarketObservation, NLPRecord
from musk_sentiment.utils.io import digest, save_records, write_json


def run_research(posts_path, nlp_path, market_dir, config_path, output, synthetic=False):
    config = load_config(config_path)
    settings = config["research"]
    assets = config["assets"]
    posts = read_posts(posts_path)
    if posts != select_window(posts, settings["start"], settings["end"]):
        raise ValueError("Use prepared study posts restricted to configured dates")
    if not posts or any(p.synthetic != synthetic for p in posts):
        raise ValueError("Empty corpus or mismatched synthetic status")
    nlp = [NLPRecord.model_validate(v) for v in json.loads(nlp_path.read_text())]
    if any(r.synthetic != synthetic for r in nlp):
        raise ValueError("Mixed empirical/synthetic NLP")
    if not synthetic:
        post_map = {p.post_id: p for p in posts}
        for record in nlp:
            post = post_map.get(record.output.post_id)
            if post is None or record.input_sha256 != digest(
                build_user_prompt(post, assets).encode()
            ):
                raise ValueError(
                    "NLP input fingerprint mismatch; rerun on this corpus and universe"
                )
    hashes = {str(p): digest(p.read_bytes()) for p in [posts_path, nlp_path, config_path]}
    all_rows = []
    all_rejections = []
    coverage = []
    for interval, key in [("1h", "hourly_horizons"), ("1d", "daily_horizons")]:
        markets = {}
        for asset in assets:
            path = market_dir / f"{asset.ticker}_{interval}.json"
            if not path.exists():
                coverage.append({"ticker": asset.ticker, "interval": interval, "status": "missing"})
                continue
            hashes[str(path)] = digest(path.read_bytes())
            markets[asset.ticker] = [
                MarketObservation.model_validate(v) for v in json.loads(path.read_text())
            ]
            if any(b.synthetic != synthetic for b in markets[asset.ticker]):
                raise ValueError("Mixed empirical/synthetic market inputs")
            coverage.append(
                {"ticker": asset.ticker, "interval": interval, "rows": len(markets[asset.ticker])}
            )
        rows, rejections = build_study(
            posts,
            nlp,
            markets,
            assets,
            interval,
            settings[key],
            settings["estimation_bars"],
            settings["min_estimation_bars"],
        )
        all_rows.extend(rows)
        all_rejections.extend(rejections)
    save_records(output / "events.json", all_rows)
    write_json(output / "rejections.json", all_rejections)
    write_json(output / "coverage.json", coverage)
    write_json(output / "descriptive.json", describe_study(all_rows, settings["seed"]))
    # Isolated-event sensitivity: clusters are calculated separately for each horizon.
    from collections import Counter, defaultdict

    groups = defaultdict(list)
    for row in all_rows:
        groups[(row.interval, row.horizon_bars)].append(row)
    isolated = []
    for group in groups.values():
        clusters = cluster_ids(group)
        counts = Counter(clusters.values())
        isolated.extend(r for r in group if counts[clusters[r.event_id]] == 1)
    write_json(output / "isolated_sensitivity.json", describe_study(isolated, settings["seed"]))
    models = evaluate_models(
        all_rows, settings["validation_start"], settings["test_start"], settings["seed"]
    )
    write_json(output / "models.json", models)
    summary = {
        "synthetic": synthetic,
        "input_sha256": hashes,
        "events": len(all_rows),
        "rejected_events": len(all_rejections),
        "posts": len(posts),
        "status": "diagnostic; requires corpus/coverage/NLP validation before research claims",
        "missing_market_files": [r for r in coverage if r.get("status") == "missing"],
        "nlp_versions": sorted({r.model + " / " + r.prompt_version for r in nlp}),
        "limitations": [
            "Observational association, not causation",
            "Modern model training may contain historical outcomes",
            "First observed mentions are left-censored by corpus start",
            "Current split-adjusted history is not a point-in-time price history",
            "No transaction-cost, execution-latency or confounder correction",
        ],
    }
    write_json(output / "manifest.json", summary)
    if not all_rows:
        raise ValueError("No valid events; see rejection and coverage reports")
    return summary


def plot_research(folder: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    manifest = json.loads((folder / "manifest.json").read_text())
    prefix = "SYNTHETIC FIXTURE — " if manifest["synthetic"] else "Exploratory — "
    data = json.loads((folder / "descriptive.json").read_text())
    keys = sorted({(r["interval"], r["horizon"], r["metric"]) for r in data})
    files = []
    for interval, horizon, metric in keys:
        rows = [
            r
            for r in data
            if (r["interval"], r["horizon"], r["metric"]) == (interval, horizon, metric)
            and r["dimension"] == "asset"
        ]
        if not rows:
            continue
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar([r["group"] for r in rows], [r["event_mean"] * 100 for r in rows], color="0.35")
        ax.axhline(0, color="black", linewidth=0.7)
        ax.set(ylabel="Return (%)", title=f"{prefix}{metric}: {horizon} × {interval} bars")
        fig.tight_layout()
        path = folder / f"{metric}_{interval}_{horizon}.png"
        fig.savefig(path, dpi=180)
        plt.close(fig)
        files.append(str(path))
    return {"figures": files}
