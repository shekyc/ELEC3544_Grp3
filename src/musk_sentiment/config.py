import tomllib
from pathlib import Path

from musk_sentiment.schemas import Asset


def load_config(path: Path) -> dict:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    config["assets"] = [Asset.model_validate(a) for a in config["assets"]]
    tickers = [a.ticker for a in config["assets"]]
    if len(tickers) != len(set(tickers)):
        raise ValueError("Duplicate configured ticker")
    if any(a.benchmark not in tickers for a in config["assets"]):
        raise ValueError("Each benchmark must have an asset configuration")
    return config
