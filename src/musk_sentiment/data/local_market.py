"""Import already-acquired USD crypto candles without silently changing quote currency."""

import csv
from datetime import UTC, datetime, timedelta

import pandas as pd

from musk_sentiment.data.alpaca import session_grid
from musk_sentiment.schemas import MarketObservation
from musk_sentiment.utils.io import save_records, snapshot, write_json


def import_crypto_csv(path, asset, interval, start, end, source, output, raw_dir):
    if asset.asset_class != "crypto":
        raise ValueError("This importer requires a configured crypto asset")
    raw = snapshot(raw_dir, path.read_bytes(), ".csv")
    expected = dict(session_grid(asset, start, end, interval))
    bars, seen = [], set()
    with path.open(newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("quote_currency") != "USD":
                raise ValueError("Every row must declare quote_currency=USD; USDT is not USD")
            if row.get("ticker") != asset.ticker:
                raise ValueError("CSV ticker must match requested ticker")
            t = row["timestamp"]
            at = (
                datetime.fromtimestamp(int(t), UTC)
                if t.isdigit()
                else pd.Timestamp(t).to_pydatetime()
            )
            if at.tzinfo is None:
                raise ValueError("Timestamp must be UTC-aware or UNIX seconds")
            at = at.astimezone(UTC)
            if at not in expected:
                if pd.Timestamp(start, tz="UTC") <= at < pd.Timestamp(end, tz="UTC"):
                    raise ValueError("Off-grid candle timestamp")
                continue
            if at in seen:
                raise ValueError("Duplicate crypto candle")
            bar = MarketObservation(
                ticker=asset.ticker,
                bar_start=at,
                bar_end=expected[at],
                interval=interval,
                **{k: float(row[k]) for k in ["open", "high", "low", "close", "volume"]},
                adjusted=False,
                source=source,
                synthetic=False,
            )
            if bar.bar_end > datetime.now(UTC):
                raise ValueError("Incomplete crypto candle")
            bars.append(bar)
            seen.add(at)
    if not bars:
        raise ValueError("No in-window crypto candles")
    bars.sort(key=lambda b: b.bar_start)
    report = {
        "source": source,
        "raw_snapshot": str(raw),
        "quote_currency": "USD",
        "expected_bars": len(expected),
        "rows": len(bars),
        "synthetic": False,
        "missing_starts": [t.isoformat() for t in expected if t not in seen],
    }
    save_records(output / f"{asset.ticker}_{interval}.json", bars)
    write_json(output / f"{asset.ticker}_{interval}_quality.json", report)
    return report


def daily_crypto(hourly):
    """Only full UTC days; no forward filling."""
    groups = {}
    for b in hourly:
        if b.interval != "1h" or b.bar_end - b.bar_start != timedelta(hours=1):
            raise ValueError("Requires full one-hour candles")
        groups.setdefault((b.ticker, b.bar_start.date()), []).append(b)
    result = []
    for (_, _day), parts in sorted(groups.items()):
        parts.sort(key=lambda b: b.bar_start)
        if len(parts) != 24 or {b.bar_start.hour for b in parts} != set(range(24)):
            continue
        if len({b.source for b in parts}) != 1:
            raise ValueError("Mixed provider daily candle")
        result.append(
            MarketObservation(
                **{
                    **parts[0].model_dump(),
                    "interval": "1d",
                    "bar_end": parts[-1].bar_end,
                    "high": max(b.high for b in parts),
                    "low": min(b.low for b in parts),
                    "close": parts[-1].close,
                    "volume": sum(b.volume for b in parts),
                    "synthetic": any(b.synthetic for b in parts),
                }
            )
        )
    return result
