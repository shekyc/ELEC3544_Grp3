"""Yahoo adapter. Never switches frequency; raw responses are content-addressed."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from musk_sentiment.alignment.calendar import session_bounds
from musk_sentiment.schemas import Asset, MarketObservation
from musk_sentiment.utils.io import save_records, snapshot, write_json


class MarketDataUnavailable(RuntimeError):
    pass


def normalize_market(
    frame: pd.DataFrame, asset: Asset, interval: str, now: datetime | None = None
) -> tuple[list[MarketObservation], list[dict]]:
    now = now or datetime.now(UTC)
    observations, rejected = [], []
    seen = set()
    for label, row in frame.iterrows():
        try:
            ts = pd.Timestamp(label)
            if interval == "1d":
                start, end = session_bounds(ts.date(), asset.calendar)
            elif interval == "1h":
                if ts.tzinfo is None:
                    raise ValueError("Intraday provider timestamp lacks timezone")
                start = ts.tz_convert("UTC").to_pydatetime()
                if asset.calendar == "24/7":
                    end = start + timedelta(hours=1)
                else:
                    opening, closing = session_bounds(ts.date(), asset.calendar)
                    if not opening <= start < closing:
                        raise ValueError("Intraday bar outside regular market hours")
                    end = min(start + timedelta(hours=1), closing)
            else:
                raise ValueError("Only 1d and 1h intervals are supported")
            if end > now:
                raise ValueError("Incomplete bar")
            if start in seen:
                raise ValueError("Duplicate market bar")
            bar = MarketObservation(
                ticker=asset.ticker,
                bar_start=start,
                bar_end=end,
                interval=interval,
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=row["Volume"],
                adjusted=True,
                source="yfinance",
                synthetic=False,
            )
            observations.append(bar)
            seen.add(start)
        except (ValueError, TypeError, KeyError) as exc:
            rejected.append({"timestamp": str(label), "reason": str(exc)})
    return sorted(observations, key=lambda b: b.bar_start), rejected


def collect_market(
    asset: Asset, start: str, end: str, interval: str, output_dir: Path, raw_dir: Path
) -> dict:
    if interval not in {"1d", "1h"}:
        raise ValueError("Choose 1d or 1h explicitly")
    if pd.Timestamp(end) <= pd.Timestamp(start):
        raise ValueError("end must follow start (end is exclusive)")
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "ticker": asset.ticker,
        "start": start,
        "end_exclusive": end,
        "requested_interval": interval,
        "provider": "yfinance",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "adjusted": True,
        "synthetic": False,
        "status": "failed",
    }
    try:
        yf.set_tz_cache_location(str(output_dir / "provider_cache"))
        # Explicit options avoid provider default changes and multi-index ambiguities.
        frame = yf.Ticker(asset.ticker).history(
            start=start,
            end=end,
            interval=interval,
            auto_adjust=True,
            actions=False,
            prepost=False,
            raise_errors=True,
            timeout=20,
        )
        if frame is None or frame.empty:
            raise MarketDataUnavailable("Provider returned no observations")
        raw = snapshot(raw_dir, frame.to_csv().encode(), ".csv")
        bars, rejected = normalize_market(frame, asset, interval)
        report.update(raw_snapshot=str(raw), rows=len(bars), rejected=rejected)
        if not bars:
            raise MarketDataUnavailable("All returned observations failed validation")
        save_records(output_dir / f"{asset.ticker}_{interval}.json", bars)
        report.update(
            status="ok",
            observed_start=bars[0].bar_start.isoformat(),
            observed_end=bars[-1].bar_end.isoformat(),
            coverage="Observed range only; completeness requires session coverage audit",
        )
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
        report["limitation"] = (
            "No frequency substitution. Historical intraday availability is limited."
        )
        write_json(output_dir / f"{asset.ticker}_{interval}_quality.json", report)
        raise MarketDataUnavailable(report["error"]) from exc
    write_json(output_dir / f"{asset.ticker}_{interval}_quality.json", report)
    return report
