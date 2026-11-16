import argparse
import json
import logging
from pathlib import Path

from musk_sentiment.analysis.run import plot_research, run_research
from musk_sentiment.config import load_config
from musk_sentiment.data.alpaca import collect_alpaca
from musk_sentiment.data.corpus import (
    compare_corpora,
    import_kaggle,
    prepare_corpus,
    read_posts,
    select_window,
)
from musk_sentiment.data.kraken import audit_crypto_coverage, collect_kraken
from musk_sentiment.data.local_market import daily_crypto, import_crypto_csv
from musk_sentiment.data.market import MarketDataUnavailable, collect_market
from musk_sentiment.data.posts import import_posts
from musk_sentiment.evaluation.annotations import sample_annotations, score_annotations
from musk_sentiment.nlp.batches import import_batch_run
from musk_sentiment.nlp.pipeline import infer
from musk_sentiment.nlp.provider import OllamaProvider
from musk_sentiment.schemas import MarketObservation
from musk_sentiment.smoke import run_smoke
from musk_sentiment.utils.io import save_records, write_json


def main(argv=None):
    parser = argparse.ArgumentParser(description="ELEC3544 reproducible research foundation")
    sub = parser.add_subparsers(dest="command", required=True)
    smoke = sub.add_parser("smoke", help="Run an entirely synthetic offline wiring test")
    smoke.add_argument("--fixture", type=Path, default=Path("tests/fixtures/posts_synthetic.csv"))
    smoke.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    smoke.add_argument("--output", type=Path, default=Path("results/smoke"))
    posts = sub.add_parser("import-posts")
    posts.add_argument("input", type=Path)
    posts.add_argument("--source", required=True, help="Dataset source URL or version identifier")
    posts.add_argument(
        "--column-map", type=Path, help="JSON mapping canonical names to CSV columns"
    )
    posts.add_argument("--source-timezone")
    posts.add_argument("--author", default="elonmusk")
    posts.add_argument("--synthetic", action="store_true")
    posts.add_argument("--output", type=Path, default=Path("data/processed/posts"))
    posts.add_argument("--raw-dir", type=Path, default=Path("data/raw/posts"))
    market = sub.add_parser("collect-market")
    market.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    market.add_argument("--tickers", nargs="+", help="Defaults to every configured asset")
    market.add_argument("--start")
    market.add_argument("--end")
    market.add_argument("--interval", choices=["1d", "1h"])
    market.add_argument("--output", type=Path, default=Path("data/processed/market"))
    market.add_argument("--raw-dir", type=Path, default=Path("data/raw/market"))
    nlp = sub.add_parser("nlp", help="Run an already-installed local Ollama model")
    nlp.add_argument("input", type=Path, help="Cleaned posts.json")
    nlp.add_argument("--model", required=True)
    nlp.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    nlp.add_argument("--output", type=Path, default=Path("data/processed/nlp"))
    nlp.add_argument("--cache", type=Path, default=Path("data/processed/nlp_cache"))
    batches = sub.add_parser("import-nlp-batches", help="Validate and import frozen agent outputs")
    batches.add_argument("run_dir", type=Path)
    batches.add_argument("--posts", type=Path, default=Path("data/processed/study/posts.json"))
    batches.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    batches.add_argument("--output", type=Path, default=Path("data/processed/nlp"))
    market.add_argument("--provider", choices=["alpaca", "yfinance"])
    market.add_argument("--asset-class", nargs="+", choices=["stock", "etf", "crypto"])
    kaggle = sub.add_parser("import-kaggle", help="Import original CSV; preserve unknown flags")
    kaggle.add_argument("input", type=Path)
    kaggle.add_argument("--output", type=Path, default=Path("data/processed/posts_full"))
    kaggle.add_argument("--raw-dir", type=Path, default=Path("data/raw/posts"))
    window = sub.add_parser("prepare-study")
    window.add_argument("input", type=Path)
    window.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    window.add_argument("--output", type=Path, default=Path("data/processed/study"))
    compare = sub.add_parser("compare-corpora")
    compare.add_argument("left", type=Path)
    compare.add_argument("right", type=Path)
    compare.add_argument(
        "--output", type=Path, default=Path("data/processed/source_comparison.json")
    )
    sample = sub.add_parser("sample-annotations")
    sample.add_argument("input", type=Path)
    sample.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    sample.add_argument("--per-quarter", type=int, default=20)
    sample.add_argument("--output", type=Path, default=Path("annotations/study_sample.csv"))
    score = sub.add_parser("score-nlp")
    score.add_argument("labels", type=Path)
    score.add_argument("predictions", type=Path)
    score.add_argument("--split", choices=["dev", "test"], default="test")
    score.add_argument("--output", type=Path, default=Path("results/nlp_evaluation.json"))
    crypto = sub.add_parser("import-crypto", help="Import explicit USD hourly/daily CSV candles")
    crypto.add_argument("input", type=Path)
    crypto.add_argument("--ticker", required=True)
    crypto.add_argument("--source", required=True)
    crypto.add_argument("--interval", choices=["1h", "1d"], required=True)
    crypto.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    crypto.add_argument("--output", type=Path, default=Path("data/processed/market"))
    crypto.add_argument("--raw-dir", type=Path, default=Path("data/raw/market"))
    daily = sub.add_parser("aggregate-crypto-daily")
    daily.add_argument("input", type=Path)
    daily.add_argument("--output", type=Path, required=True)
    research = sub.add_parser("research", help="Offline event study and chronological models")
    research.add_argument("--posts", type=Path, default=Path("data/processed/study/posts.json"))
    research.add_argument("--nlp", type=Path, default=Path("data/processed/nlp/sentiments.json"))
    research.add_argument("--market-dir", type=Path, default=Path("data/processed/market"))
    research.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    research.add_argument("--output", type=Path, default=Path("results/study"))
    research.add_argument("--synthetic", action="store_true")
    plots = sub.add_parser("plot-study")
    plots.add_argument("input", type=Path)
    score.add_argument(
        "--reference-type",
        choices=["model", "human", "mixed", "unspecified"],
        default="unspecified",
    )
    kraken = sub.add_parser(
        "collect-kraken", help="Download native hourly/daily USD crypto archives"
    )
    kraken.add_argument("--config", type=Path, default=Path("configs/project.toml"))
    kraken.add_argument("--output", type=Path, default=Path("data/processed/market"))
    kraken.add_argument("--raw-dir", type=Path, default=Path("data/raw/kraken"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        if args.command == "smoke":
            result = run_smoke(args.fixture, args.config, args.output)
        elif args.command == "import-posts":
            mapping = json.loads(args.column_map.read_text()) if args.column_map else None
            _, result = import_posts(
                args.input,
                args.output,
                args.raw_dir,
                args.source,
                mapping,
                args.source_timezone,
                args.author,
                args.synthetic,
            )
        elif args.command == "collect-market":
            config = load_config(args.config)
            assets = config["assets"]
            if args.tickers:
                unknown = set(args.tickers) - {a.ticker for a in assets}
                if unknown:
                    raise ValueError(f"Unconfigured tickers: {sorted(unknown)}")
                assets = [a for a in assets if a.ticker in args.tickers]
            if args.asset_class:
                assets = [a for a in assets if a.asset_class in args.asset_class]
            collector = (
                collect_alpaca
                if (args.provider or config["research"].get("provider")) == "alpaca"
                else collect_market
            )
            result, failures = [], []
            for asset in assets:
                try:
                    result.append(
                        collector(
                            asset,
                            args.start
                            or config["research"].get("market_start", config["research"]["start"]),
                            args.end
                            or config["research"].get("market_end", config["research"]["end"]),
                            args.interval or config["research"]["interval"],
                            args.output,
                            args.raw_dir,
                        )
                    )
                except MarketDataUnavailable as exc:
                    failures.append({"ticker": asset.ticker, "error": str(exc)})
            write_json(
                args.output / "run_summary.json", {"successes": result, "failures": failures}
            )
            if failures:
                raise ValueError(f"{len(failures)} asset downloads failed; see run_summary.json")
        elif args.command == "import-kaggle":
            result = import_kaggle(args.input, args.output, args.raw_dir)
        elif args.command == "prepare-study":
            settings = load_config(args.config)["research"]
            result = prepare_corpus(args.input, args.output, settings["start"], settings["end"])
        elif args.command == "compare-corpora":
            result = compare_corpora(args.left, args.right)
            write_json(args.output, result)
        elif args.command == "sample-annotations":
            cfg = load_config(args.config)
            posts = select_window(
                read_posts(args.input), cfg["research"]["start"], cfg["research"]["end"]
            )
            result = sample_annotations(
                posts, cfg["assets"], args.output, args.per_quarter, cfg["research"]["seed"]
            )
        elif args.command == "score-nlp":
            result = score_annotations(
                args.labels, args.predictions, args.split, args.reference_type
            )
            write_json(args.output, result)
        elif args.command == "collect-kraken":
            cfg = load_config(args.config)
            manifest = collect_kraken(
                cfg["assets"],
                cfg["research"]["market_start"],
                cfg["research"]["market_end"],
                args.output,
                args.raw_dir,
            )
            audit_crypto_coverage(
                args.output, cfg["assets"], cfg["research"]["start"], cfg["research"]["end"]
            )
            result = {
                "status": manifest["status"],
                "downloaded_bytes": manifest["downloaded_bytes"],
                "series": [
                    {
                        "ticker": a["ticker"],
                        "interval": a["interval"],
                        "rows": a["rows"],
                        "missing": len(a["missing_starts"]),
                    }
                    for a in manifest["assets"]
                ],
            }
        elif args.command == "import-crypto":
            cfg = load_config(args.config)
            asset = next((a for a in cfg["assets"] if a.ticker == args.ticker), None)
            if asset is None:
                raise ValueError("Unconfigured crypto ticker")
            result = import_crypto_csv(
                args.input,
                asset,
                args.interval,
                cfg["research"]["market_start"],
                cfg["research"]["market_end"],
                args.source,
                args.output,
                args.raw_dir,
            )
        elif args.command == "aggregate-crypto-daily":
            bars = [MarketObservation.model_validate(v) for v in json.loads(args.input.read_text())]
            daily_bars = daily_crypto(bars)
            save_records(args.output, daily_bars)
            result = {"daily_bars": len(daily_bars), "input_hours": len(bars)}
        elif args.command == "research":
            result = run_research(
                args.posts, args.nlp, args.market_dir, args.config, args.output, args.synthetic
            )
        elif args.command == "plot-study":
            result = plot_research(args.input)
        elif args.command == "import-nlp-batches":
            result = import_batch_run(args.run_dir, args.posts, args.config, args.output)
        elif args.command == "nlp":
            cfg = load_config(args.config)
            assets = cfg["assets"]
            provider = OllamaProvider(args.model)
            records, errors = [], []
            posts = read_posts(args.input)
            if posts != select_window(posts, cfg["research"]["start"], cfg["research"]["end"]):
                raise ValueError("NLP input outside study window; run prepare-study first")
            for post in posts:
                try:
                    records.append(infer(post, assets, provider, args.cache))
                except RuntimeError as exc:
                    errors.append({"post_id": post.post_id, "error": str(exc)})
            save_records(args.output / "sentiments.json", records)
            write_json(args.output / "errors.json", errors)
            if errors:
                raise ValueError(f"{len(errors)} NLP failures; successful outputs cached for retry")
            result = {"processed": len(records), "provider": provider.name, "model": provider.model}
        print(json.dumps(result, indent=2))
    except Exception as exc:
        logging.error("%s: %s", type(exc).__name__, exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
