"""Separate one-minute acquisition; existing hourly/daily artifacts are never overwritten."""

import csv
import io
import json
import os
import time
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import httpx

from musk_sentiment.data.kraken import PART_URLS, RemoteArchive
from musk_sentiment.schemas import MinuteBar
from musk_sentiment.utils.io import digest, snapshot, write_json


def publish_minutes(rows, ticker, output, provenance):
    """Validate compact rows, reject duplicates, and publish content-hashed daily JSON files."""
    grouped = defaultdict(list)
    seen = set()
    for raw in rows:
        bar = MinuteBar.model_validate(raw)
        if bar.t in seen:
            raise ValueError(f"Duplicate minute: {ticker} {bar.t}")
        seen.add(bar.t)
        grouped[bar.t.date().isoformat()].append(bar)
    files = []
    for day, bars in sorted(grouped.items()):
        bars.sort(key=lambda b: b.t)
        path = output / ticker / f"{day}.json"
        payload = [b.model_dump(mode="json", exclude={"schema_version", "vw"}) for b in bars]
        # VWAP is optional and is retained where the provider supplied it.
        for row, bar in zip(payload, bars, strict=True):
            if bar.vw is not None:
                row["vw"] = bar.vw
        if path.exists() and json.loads(path.read_text()) != payload:
            raise ValueError(f"Refusing to replace different minute data: {path}")
        write_json(path, payload)
        files.append({"path": str(path), "sha256": digest(path.read_bytes()), "rows": len(bars)})
    report = {
        **provenance,
        "ticker": ticker,
        "interval": "1min",
        "synthetic": False,
        "timestamp": "UTC minute start; end=start+60 seconds",
        "volume_units": "base asset units; split-adjusted shares for Alpaca",
        "missing_policy": "No price/volume/trade-count filling",
        "rows": len(seen),
        "daily_files": files,
    }
    write_json(output / ticker / "manifest.json", report)
    return report


def collect_stock_minutes(ticker, start, end, output, raw_dir):
    """Collect explicit historical SIP minute bars with pagination and resumable raw pages."""
    headers = {
        "APCA-API-KEY-ID": os.environ["APCA_API_KEY_ID"],
        "APCA-API-SECRET-KEY": os.environ["APCA_API_SECRET_KEY"],
    }
    params = {
        "symbols": ticker,
        "timeframe": "1Min",
        "feed": "sip",
        "adjustment": "split",
        "start": start + "T00:00:00Z",
        "end": end + "T00:00:00Z",
        "limit": 10000,
        "sort": "asc",
    }
    pages, tokens, rows = [], set(), []
    checkpoint = raw_dir / f"{ticker}_{start}_{end}_pages.json"
    saved = json.loads(checkpoint.read_text()) if checkpoint.exists() else []
    index = 0
    with httpx.Client(timeout=60) as client:
        while True:
            if index < len(saved):
                page = saved[index]
                if page["request"] != params:
                    raise ValueError("Minute checkpoint request mismatch")
                payload_bytes = Path(page["snapshot"]).read_bytes()
                if digest(payload_bytes) != page["sha256"]:
                    raise ValueError("Minute checkpoint hash mismatch")
                payload = json.loads(payload_bytes)
            else:
                for attempt in range(5):
                    response = client.get(
                        "https://data.alpaca.markets/v2/stocks/bars", params=params, headers=headers
                    )
                    if response.status_code not in {429, 500, 502, 503, 504}:
                        break
                    time.sleep(min(2**attempt, 16))
                if response.status_code != 200:
                    raise ValueError(f"Alpaca minute HTTP {response.status_code}")
                payload = response.json()
                page = {
                    "request": dict(params),
                    "snapshot": str(snapshot(raw_dir, response.content, ".json")),
                    "sha256": digest(response.content),
                }
                saved.append(page)
                write_json(checkpoint, saved)
                time.sleep(0.35)
            pages.append(page)
            rows.extend((payload.get("bars") or {}).get(ticker, []))
            index += 1
            if index % 20 == 0:
                print(f"{ticker}: {index} pages, {len(rows)} minute bars", flush=True)
            token = payload.get("next_page_token")
            if not token:
                break
            if token in tokens:
                raise ValueError("Repeated minute pagination token")
            tokens.add(token)
            params["page_token"] = token
    if not rows:
        raise ValueError(f"No minute data: {ticker}")
    records = [
        {k: r[k] for k in ("t", "o", "h", "l", "c", "v", "n", "vw") if k in r}
        for r in rows
        if start <= r["t"][:10] < end
    ]
    return publish_minutes(
        records,
        ticker,
        output,
        {
            "provider": "alpaca:sip:split",
            "start": start,
            "end_exclusive": end,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "raw_pages": pages,
        },
    )


class CachedMinuteArchive(RemoteArchive):
    """Reuse the verified availability-probe bytes; bound any necessary network read."""

    def __init__(self, raw_dir, probe=None, directory=None):
        self.cached = {}
        self.cached_parts = {}
        if probe and probe.exists():
            data = json.loads(probe.read_text())
            self.cached = {(r["url"], r["start"], r["length"]): r for r in data["range_requests"]}
        if directory and directory.exists():
            data = json.loads(directory.read_text())
            self.cached_parts = {p["url"]: p for p in data["parts"]}
        super().__init__(PART_URLS, raw_dir)

    def _request(self, url, start, length, etag=None):
        cached = self.cached.get((url, start, length))
        part = self.cached_parts.get(url)
        if cached and part:
            payload = Path(cached["raw_snapshot"]).read_bytes()
            if digest(payload) != cached["sha256"] or (etag and etag != part["etag"]):
                raise ValueError("Cached archive integrity failure")
            self.requests.append(cached)
            return payload, {
                "content-range": f"bytes {start}-{start + length - 1}/{part['size']}",
                "etag": part["etag"],
                "last-modified": part["last_modified"],
            }
        return super()._request(url, start, length, etag)

    def read(self, size=-1):
        if size > 160_000_000:
            raise ValueError("Unexpectedly large minute archive member")
        if size <= 16_000_000:
            return super().read(size)
        chunks = []
        while size:
            chunk = super().read(min(size, 16_000_000))
            chunks.append(chunk)
            size -= len(chunk)
            if not chunk:
                break
        return b"".join(chunks)


def collect_crypto_minutes(start, end, output, raw_dir, probe_dir):
    """Extract native BTC/DOGE USD minutes; CRC-check full members, retain provider gaps."""
    archive = CachedMinuteArchive(
        raw_dir,
        probe_dir / "kraken_probe.json",
        probe_dir / "kraken_directory.json",
    )
    reports = []
    lo = datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp()
    hi = datetime.fromisoformat(end).replace(tzinfo=UTC).timestamp()
    with zipfile.ZipFile(archive) as zipped:
        for ticker, member in [("BTC-USD", "XBTUSD_1.csv"), ("DOGE-USD", "XDGUSD_1.csv")]:
            payload = zipped.read(member)
            rows = []
            for row in csv.reader(io.StringIO(payload.decode())):
                at = int(row[0])
                if lo <= at < hi:
                    rows.append(
                        dict(
                            t=datetime.fromtimestamp(at, UTC),
                            o=float(row[1]),
                            h=float(row[2]),
                            l=float(row[3]),
                            c=float(row[4]),
                            v=float(row[5]),
                            n=int(row[6]),
                        )
                    )
            reports.append(
                publish_minutes(
                    rows,
                    ticker,
                    output,
                    {
                        "provider": "kraken:spot:USD:OHLCVT",
                        "start": start,
                        "end_exclusive": end,
                        "member": member,
                        "member_sha256": digest(payload),
                        "crc32_verified": True,
                        "raw_ranges": archive.requests.copy(),
                    },
                )
            )
            print(ticker, reports[-1]["rows"], "minute bars published", flush=True)
    return reports
