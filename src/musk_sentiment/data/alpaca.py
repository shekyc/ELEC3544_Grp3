"""Explicit SIP history, immutable pages, and complete regular-session aggregation."""

import os
import time
from datetime import UTC, datetime
from pathlib import Path

import exchange_calendars as xcals
import httpx
import pandas as pd

from musk_sentiment.data.market import MarketDataUnavailable
from musk_sentiment.schemas import Asset, MarketObservation
from musk_sentiment.utils.io import save_records, snapshot, write_json


def session_grid(asset: Asset, start: str, end: str, interval: str):
    """Expected UTC boundaries; hourly securities bars are anchored at session open."""
    lo, hi = pd.Timestamp(start, tz="UTC"), pd.Timestamp(end, tz="UTC")
    if hi <= lo or interval not in {"1h", "1d", "30Min"}:
        raise ValueError("Invalid market range or interval")
    if asset.calendar == "24/7":
        step = {"1h": "1h", "1d": "1D", "30Min": "30min"}[interval]
        return [
            (t.to_pydatetime(), (t + pd.Timedelta(step)).to_pydatetime())
            for t in pd.date_range(lo, hi, freq=step, inclusive="left")
        ]
    cal = xcals.get_calendar(asset.calendar, start=lo.date(), end=hi.date())
    result = []
    for day in cal.sessions:
        opening, closing = cal.session_open(day), cal.session_close(day)
        if not lo <= opening < hi:
            continue
        if interval == "1d":
            result.append((opening.to_pydatetime(), closing.to_pydatetime()))
        else:
            step = pd.Timedelta(minutes=30 if interval == "30Min" else 60)
            for t in pd.date_range(opening, closing, freq=step, inclusive="left"):
                result.append((t.to_pydatetime(), min(t + step, closing).to_pydatetime()))
    return result


def aggregate_sip(rows, asset, start, end, interval, now=None):
    """Use 30-minute inputs so the 09:00 premarket bar cannot contaminate 09:30."""
    now = now or datetime.now(UTC)
    expected_half = {a: b for a, b in session_grid(asset, start, end, "30Min")}
    halves, rejected = {}, []
    duplicates = set()
    for row in rows:
        try:
            at = pd.Timestamp(row["t"]).to_pydatetime()
            if at.tzinfo is None:
                raise ValueError("Naive provider timestamp")
            at = at.astimezone(UTC)
            if at not in expected_half:
                continue  # extended hours are deliberately excluded
            if at in halves or at in duplicates:
                halves.pop(at, None)
                duplicates.add(at)
                raise ValueError("Duplicate SIP bar; all copies excluded")
            bar = MarketObservation(
                ticker=asset.ticker,
                bar_start=at,
                bar_end=expected_half[at],
                interval="1h",
                open=row["o"],
                high=row["h"],
                low=row["l"],
                close=row["c"],
                volume=row["v"],
                adjusted=True,
                source="alpaca:sip:split:30Min",
                synthetic=False,
            )
            if bar.bar_end > now:
                raise ValueError("Incomplete provider bar")
            halves[at] = bar
        except (KeyError, ValueError, TypeError) as exc:
            rejected.append({"timestamp": str(row.get("t")), "reason": str(exc)})
    bars, missing = [], []
    for opening, closing in session_grid(asset, start, end, interval):
        slots = [
            t.to_pydatetime()
            for t in pd.date_range(opening, closing, freq="30min", inclusive="left")
        ]
        if any(t not in halves for t in slots):
            missing.append(opening.isoformat())
            continue
        parts = [halves[t] for t in slots]
        bars.append(
            MarketObservation(
                ticker=asset.ticker,
                bar_start=opening,
                bar_end=closing,
                interval=interval,
                open=parts[0].open,
                high=max(b.high for b in parts),
                low=min(b.low for b in parts),
                close=parts[-1].close,
                volume=sum(b.volume for b in parts),
                adjusted=True,
                source="alpaca:sip:split:rth-from-30Min",
                synthetic=False,
            )
        )
    return bars, {
        "expected_bars": len(bars) + len(missing),
        "missing_starts": missing,
        "rejected": rejected,
        "rows": len(bars),
    }


def collect_alpaca(asset, start, end, interval, output_dir: Path, raw_dir: Path, client=None):
    if asset.asset_class == "crypto":
        raise MarketDataUnavailable(
            "Alpaca crypto 2020 coverage unverified; import audited USD bars"
        )
    if interval not in {"1h", "1d"} or pd.Timestamp(end) <= pd.Timestamp(start):
        raise ValueError("Invalid dates or interval")
    key, secret = os.environ.get("APCA_API_KEY_ID"), os.environ.get("APCA_API_SECRET_KEY")
    if not key or not secret:
        raise MarketDataUnavailable("Set APCA_API_KEY_ID and APCA_API_SECRET_KEY locally")
    params = {
        "symbols": asset.ticker,
        "timeframe": "30Min",
        "feed": "sip",
        "adjustment": "split",
        "sort": "asc",
        "limit": 10000,
        "start": f"{start}T00:00:00Z",
        "end": (pd.Timestamp(end, tz="UTC") - pd.Timedelta(microseconds=1)).isoformat(),
    }
    report = {
        "ticker": asset.ticker,
        "provider": "alpaca",
        "feed": "sip",
        "adjustment": "split",
        "start": start,
        "end_exclusive": end,
        "interval": interval,
        "request_timeframe": "30Min",
        "synthetic": False,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "raw_snapshots": [],
    }
    own_client = client is None
    client = client or httpx.Client(timeout=60)
    rows, tokens = [], set()
    try:
        while True:
            for attempt in range(4):
                response = client.get(
                    "https://data.alpaca.markets/v2/stocks/bars",
                    params=params,
                    headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret},
                )
                if response.status_code not in {429, 500, 502, 503, 504}:
                    break
                time.sleep(min(2**attempt, 8))
            if response.status_code != 200:
                raise MarketDataUnavailable(
                    f"Alpaca HTTP {response.status_code}; "
                    "check credentials, SIP entitlement, dates or rate limits"
                )
            report["raw_snapshots"].append(str(snapshot(raw_dir, response.content, ".json")))
            payload = response.json()
            rows.extend((payload.get("bars") or {}).get(asset.ticker, []))
            token = payload.get("next_page_token")
            if not token:
                break
            if token in tokens:
                raise MarketDataUnavailable("Repeated Alpaca pagination token")
            tokens.add(token)
            params["page_token"] = token
            time.sleep(0.31)  # Basic plan: keep sustained request rate under 200/minute
        bars, quality = aggregate_sip(rows, asset, start, end, interval)
        report.update(quality)
        if not bars:
            raise MarketDataUnavailable("No complete regular-session bars returned")
        report["status"] = "complete" if not quality["missing_starts"] else "gaps"
        save_records(output_dir / f"{asset.ticker}_{interval}.json", bars)
    except Exception as exc:
        report.update(status="failed", error=str(exc))
        raise MarketDataUnavailable(str(exc)) from exc
    finally:
        write_json(output_dir / f"{asset.ticker}_{interval}_quality.json", report)
        if own_client:
            client.close()
    return report
