import io
import re
import zipfile
from email.message import Message

import pytest

from musk_sentiment.data.kraken import RemoteArchive, parse_candles
from musk_sentiment.schemas import Asset


def asset():
    return Asset(ticker="DOGE-USD", asset_class="crypto", calendar="24/7", benchmark="BTC-USD")


def test_native_candles_preserve_no_trade_gaps():
    payload = b"1577836800,1,2,1,2,10,2\n1577844000,2,3,1,2,15,3\n"
    bars, missing = parse_candles(payload, asset(), "2020-01-01", "2020-01-02")
    assert len(bars) == 2 and len(missing) == 22
    assert "2020-01-01T01:00:00+00:00" in missing
    assert bars[0].source == "kraken:spot:USD:OHLCVT:60min"
    assert not bars[0].synthetic and not bars[0].adjusted
    # Native daily is valid even if that day's hourly file has no-trade gaps.
    daily, gaps = parse_candles(
        b"1577836800,1,3,1,2,25,5\n", asset(), "2020-01-01", "2020-01-02", "1d"
    )
    assert len(daily) == 1 and not gaps and daily[0].volume == 25
    assert daily[0].source.endswith("1440min")


def test_kraken_rejects_duplicate_offgrid_and_malformed():
    row = b"1577836800,1,2,1,2,10,2\n"
    with pytest.raises(ValueError, match="Duplicate"):
        parse_candles(row + row, asset(), "2020-01-01", "2020-01-02")
    with pytest.raises(ValueError, match="Off-grid"):
        parse_candles(
            row.replace(b"1577836800", b"1577836801"), asset(), "2020-01-01", "2020-01-02"
        )
    with pytest.raises(ValueError, match="seven"):
        parse_candles(b"1577836800,1,2\n", asset(), "2020-01-01", "2020-01-02")


class Response(io.BytesIO):
    def __init__(self, data, start, end, total, status=206, etag="stable"):
        super().__init__(data)
        self.status = status
        self.headers = Message()
        self.headers["content-range"] = f"bytes {start}-{end}/{total}"
        self.headers["etag"] = etag
        self.headers["last-modified"] = "fixture"


def test_remote_split_zip_and_header_case(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("XDGUSD_60.csv", "1577836800,1,2,1,2,10,2\n")
    payload = buffer.getvalue()
    cut = len(payload) // 2
    parts = {"https://example.test/0": payload[:cut], "https://example.test/1": payload[cut:]}

    def opener(request, timeout):
        content = parts[request.full_url]
        start, end = map(
            int, re.fullmatch(r"bytes=(\d+)-(\d+)", request.get_header("Range")).groups()
        )
        return Response(content[start : end + 1], start, end, len(content))

    with RemoteArchive(list(parts), tmp_path, opener=opener) as stream:
        with zipfile.ZipFile(stream) as z:
            assert z.read("XDGUSD_60.csv") == b"1577836800,1,2,1,2,10,2\n"
        assert len(stream.parts) == 2 and stream.parts[0]["etag"] == "stable"
        assert stream.requests and list(tmp_path.glob("*.range.bin"))


def test_range_server_must_honor_request(tmp_path):
    def bad(request, timeout):
        return Response(b"x", 0, 0, 10, status=200)

    with pytest.raises(ValueError, match="ignored"):
        RemoteArchive(["https://example.test/a"], tmp_path, opener=bad)


def test_changed_archive_etag_rejected(tmp_path):
    calls = 0

    def changing(request, timeout):
        nonlocal calls
        calls += 1
        return Response(b"x", 0, 0, 10, etag="stable" if calls == 1 else "changed")

    stream = RemoteArchive(["https://example.test/a"], tmp_path, opener=changing)
    with pytest.raises(ValueError, match="changed during"):
        stream.read(1)


def test_study_audit_distinguishes_sparse_hours_and_complete_native_day(tmp_path):
    from musk_sentiment.data.kraken import audit_crypto_coverage
    from musk_sentiment.utils.io import save_records

    bars, _ = parse_candles(
        b"1577836800,1,2,1,2,10,2\n1577844000,2,3,1,2,15,3\n", asset(), "2020-01-01", "2020-01-02"
    )
    daily, _ = parse_candles(
        b"1577836800,1,3,1,2,25,5\n", asset(), "2020-01-01", "2020-01-02", "1d"
    )
    save_records(tmp_path / "DOGE-USD_1h.json", bars)
    save_records(tmp_path / "DOGE-USD_1d.json", daily)
    report = audit_crypto_coverage(tmp_path, [asset()], "2020-01-01", "2020-01-02")
    assert report["series"][0]["study_missing"] == 22
    assert report["series"][1]["study_missing"] == 0
    import json

    consistency = json.loads((tmp_path / "crypto_cross_frequency_audit.json").read_text())
    assert consistency[0]["matching_days_with_missing_hours"] == 1
    assert not consistency[0]["mismatches"]
