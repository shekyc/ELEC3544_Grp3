import argparse
import json
import logging
from pathlib import Path

from musk_sentiment.config import load_config
from musk_sentiment.data.market import MarketDataUnavailable, collect_market
from musk_sentiment.data.posts import import_posts
from musk_sentiment.nlp.pipeline import infer
from musk_sentiment.nlp.provider import OllamaProvider
from musk_sentiment.schemas import CleanPost
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
            result, failures = [], []
            for asset in assets:
                try:
                    result.append(
                        collect_market(
                            asset,
                            args.start or config["research"]["start"],
                            args.end or config["research"]["end"],
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
        else:
            assets = load_config(args.config)["assets"]
            provider = OllamaProvider(args.model)
            records, errors = [], []
            for value in json.loads(args.input.read_text()):
                post = CleanPost.model_validate(value)
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
