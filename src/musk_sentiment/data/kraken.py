"""Public Kraken USD archives, read by HTTP ranges without downloading the 9.5 GB ZIP."""

import bisect
import csv
import io
import time
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from musk_sentiment.data.alpaca import session_grid
from musk_sentiment.schemas import MarketObservation
from musk_sentiment.utils.io import digest, save_records, snapshot, write_json

BASE = "https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_Full.zip.part"
PART_URLS = [BASE + f"{i:02}" for i in range(5)]
MEMBERS = {"BTC-USD": "XBTUSD_60.csv", "ETH-USD": "ETHUSD_60.csv", "DOGE-USD": "XDGUSD_60.csv"}
SOURCE = "kraken:spot:USD:OHLCVT:60min"


class RemoteArchive(io.RawIOBase):
    """Seekable concatenated public files; enforce ranges, bounded reads and stable ETags."""

    def __init__(self, urls, raw_dir: Path, opener=urllib.request.urlopen):
        self.urls = urls
        self.raw_dir = raw_dir
        self.opener = opener
        self.position = 0
        self.parts = []
        self.requests = []
        self.offsets = [0]
        for url in urls:
            body, headers = self._request(url, 0, 1)
            total = int(headers["content-range"].rsplit("/", 1)[1])
            self.parts.append(
                {
                    "url": url,
                    "size": total,
                    "etag": headers.get("etag"),
                    "last_modified": headers.get("last-modified"),
                }
            )
            self.offsets.append(self.offsets[-1] + total)

    def _request(self, url, start, length, etag=None):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Range": f"bytes={start}-{start + length - 1}",
                "Accept-Encoding": "identity",
            },
        )
        for attempt in range(3):
            try:
                with self.opener(request, timeout=60) as response:
                    content_range = response.headers.get("Content-Range", "")
                    if response.status != 206 or not content_range.startswith(
                        f"bytes {start}-{start + length - 1}/"
                    ):
                        raise ValueError("Server ignored or changed requested archive byte range")
                    if etag and response.headers.get("etag") != etag:
                        raise ValueError(
                            "Archive changed during extraction; retry from a fresh run"
                        )
                    payload = response.read(length + 1)
                    if len(payload) != length:
                        raise ValueError("Truncated archive byte range")
                    headers = {k.lower(): v for k, v in response.headers.items()}
                raw = snapshot(self.raw_dir, payload, ".range.bin")
                self.requests.append(
                    {
                        "url": url,
                        "start": start,
                        "length": length,
                        "sha256": digest(payload),
                        "raw_snapshot": str(raw),
                    }
                )
                return payload, headers
            except urllib.error.HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                time.sleep(2**attempt)
        raise AssertionError("unreachable")

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=0):
        if whence not in {0, 1, 2}:
            raise ValueError("Invalid seek mode")
        target = offset + (0 if whence == 0 else self.position if whence == 1 else self.offsets[-1])
        if target < 0:
            raise ValueError("Negative archive offset")
        self.position = target
        return self.position

    def read(self, size=-1):
        if size < 0:
            size = max(0, self.offsets[-1] - self.position)
        if size > 32_000_000:
            raise ValueError("Refusing unexpectedly large archive range")
        chunks = []
        while size and self.position < self.offsets[-1]:
            part = bisect.bisect_right(self.offsets, self.position) - 1
            offset = self.position - self.offsets[part]
            length = min(size, self.parts[part]["size"] - offset)
            chunk, _ = self._request(self.urls[part], offset, length, self.parts[part]["etag"])
            chunks.append(chunk)
            self.position += length
            size -= length
        return b"".join(chunks)


def parse_candles(payload: bytes, asset, start, end, interval="1h"):
    """Kraken timestamps are UNIX seconds; volume is base-asset quantity, not USD."""
    if asset.ticker not in MEMBERS or asset.asset_class != "crypto":
        raise ValueError("Only verified Kraken BTC/USD, ETH/USD and DOGE/USD mappings supported")
    expected = dict(session_grid(asset, start, end, interval))
    bars = []
    seen = set()
    lower, upper = min(expected), max(expected.values())
    for line, row in enumerate(csv.reader(io.StringIO(payload.decode("utf-8-sig"))), 1):
        if len(row) != 7:
            raise ValueError(f"Kraken row {line} must have seven OHLCVT fields")
        at = datetime.fromtimestamp(int(row[0]), UTC)
        if at not in expected:
            if lower <= at < upper:
                raise ValueError(f"Off-grid Kraken timestamp on row {line}")
            continue
        if at in seen:
            raise ValueError(f"Duplicate Kraken hour on row {line}")
        if int(row[6]) < 0:
            raise ValueError("Negative trade count")
        bars.append(
            MarketObservation(
                ticker=asset.ticker,
                bar_start=at,
                bar_end=expected[at],
                interval=interval,
                **{
                    key: float(value)
                    for key, value in zip(
                        ["open", "high", "low", "close", "volume"], row[1:6], strict=True
                    )
                },
                adjusted=False,
                source=SOURCE if interval == "1h" else SOURCE.replace("60min", "1440min"),
                synthetic=False,
            )
        )
        seen.add(at)
    bars.sort(key=lambda b: b.bar_start)
    return bars, sorted(t.isoformat() for t in set(expected) - seen)


def collect_kraken(assets, start, end, output: Path, raw_dir: Path, urls=None):
    """Fetch native hourly and daily USD members, never filling absent no-trade hours."""
    assets = [a for a in assets if a.asset_class == "crypto"]
    if not assets or any(a.ticker not in MEMBERS for a in assets):
        raise ValueError("Unverified crypto mapping in configured universe")
    manifest = {
        "provider": "Kraken",
        "quote_currency": "USD",
        "synthetic": False,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "start": start,
        "end_exclusive": end,
        "archive_urls": urls or PART_URLS,
        "assets": [],
        "status": "running",
        "integrity": "ZIP member CRC verified; range/member SHA256 recorded. "
        "Full multi-GB archive SHA256 not verified because only ranges downloaded.",
    }
    archive = None
    try:
        archive = RemoteArchive(urls or PART_URLS, raw_dir / "ranges")
        with zipfile.ZipFile(archive) as zipped:
            for asset in assets:
                for interval, minutes in [("1h", "60"), ("1d", "1440")]:
                    member = MEMBERS[asset.ticker].replace("_60.csv", f"_{minutes}.csv")
                    info = zipped.getinfo(member)
                    if info.file_size > 32_000_000:
                        raise ValueError("Unexpectedly large CSV member")
                    payload = zipped.read(member)  # verifies ZIP member CRC
                    raw = snapshot(raw_dir, payload, ".csv")
                    bars, missing = parse_candles(payload, asset, start, end, interval)
                    if not bars:
                        raise ValueError(f"No requested data in {member}")
                    report = {
                        "ticker": asset.ticker,
                        "interval": interval,
                        "provider": "Kraken",
                        "source": bars[0].source,
                        "member": member,
                        "member_crc32": f"{info.CRC:08x}",
                        "member_sha256": digest(payload),
                        "raw_snapshot": str(raw),
                        "rows": len(bars),
                        "missing_starts": missing,
                        "expected_bars": len(bars) + len(missing),
                        "start": start,
                        "end_exclusive": end,
                        "quote_currency": "USD",
                        "volume_unit": asset.ticker.split("-")[0],
                        "synthetic": False,
                        "status": "complete" if not missing else "gaps",
                        "zero_volume_bars": sum(b.volume == 0 for b in bars),
                        "gap_policy": "Native provider candles; no forward filling. "
                        "Kraken omits intervals with no trades.",
                    }
                    save_records(output / f"{asset.ticker}_{interval}.json", bars)
                    write_json(output / f"{asset.ticker}_{interval}_quality.json", report)
                    manifest["assets"].append(report)
        manifest["status"] = (
            "complete_with_documented_gaps"
            if any(a["missing_starts"] for a in manifest["assets"])
            else "complete"
        )
    except Exception as exc:
        manifest.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        if archive:
            manifest["parts"] = archive.parts
            manifest["requests"] = archive.requests
            manifest["downloaded_bytes"] = sum(r["length"] for r in archive.requests)
            archive.close()
        write_json(output / "kraken_manifest.json", manifest)
    return manifest


def audit_crypto_coverage(output: Path, assets, study_start, study_end):
    """Report study-window gaps and compare native daily OHLCV with available hourly trades."""
    import json
    import math
    from collections import Counter, defaultdict

    series, consistency = [], []
    for asset in assets:
        if asset.asset_class != "crypto":
            continue
        records = {}
        for interval in ["1h", "1d"]:
            bars = [
                MarketObservation.model_validate(v)
                for v in json.loads((output / f"{asset.ticker}_{interval}.json").read_text())
            ]
            records[interval] = bars
            expected = {a for a, b in session_grid(asset, study_start, study_end, interval)}
            present = {b.bar_start for b in bars} & expected
            missing = sorted(expected - present)
            series.append(
                {
                    "ticker": asset.ticker,
                    "interval": interval,
                    "study_rows": len(present),
                    "study_missing": len(missing),
                    "expected": len(expected),
                    "monthly_missing": dict(
                        sorted(Counter(t.strftime("%Y-%m") for t in missing).items())
                    ),
                    "full_buffer_rows": len(bars),
                    "synthetic": False,
                }
            )
        groups = defaultdict(list)
        for bar in records["1h"]:
            groups[bar.bar_start.date()].append(bar)
        matched = sparse_matched = 0
        mismatches = []
        for day in records["1d"]:
            parts = sorted(groups.get(day.bar_start.date(), []), key=lambda b: b.bar_start)
            if not parts:
                continue
            values = {
                "open": parts[0].open,
                "close": parts[-1].close,
                "high": max(b.high for b in parts),
                "low": min(b.low for b in parts),
                "volume": sum(b.volume for b in parts),
            }
            bad = [
                k
                for k, v in values.items()
                if not math.isclose(v, getattr(day, k), rel_tol=1e-7, abs_tol=1e-7)
            ]
            if bad:
                mismatches.append({"day": day.bar_start.date().isoformat(), "fields": bad})
            else:
                matched += 1
                sparse_matched += int(len(parts) < 24)
        consistency.append(
            {
                "ticker": asset.ticker,
                "days_compared": matched + len(mismatches),
                "matching_days": matched,
                "matching_days_with_missing_hours": sparse_matched,
                "mismatches": mismatches,
                "synthetic": False,
            }
        )
    report = {
        "source": "Kraken spot USD",
        "study_start": study_start,
        "study_end_exclusive": study_end,
        "series": series,
        "synthetic": False,
    }
    write_json(output / "crypto_study_coverage.json", report)
    write_json(output / "crypto_cross_frequency_audit.json", consistency)
    return report
