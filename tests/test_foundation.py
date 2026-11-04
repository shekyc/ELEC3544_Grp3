import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from musk_sentiment.alignment.calendar import next_trading_time, session_bounds
from musk_sentiment.analysis.returns import benchmark_adjusted, simple_return
from musk_sentiment.config import load_config
from musk_sentiment.data.market import MarketDataUnavailable, collect_market, normalize_market
from musk_sentiment.data.posts import import_posts, timestamp
from musk_sentiment.features.validation import purged_split
from musk_sentiment.nlp.pipeline import infer
from musk_sentiment.nlp.provider import SyntheticProvider
from musk_sentiment.schemas import (
    AssetSentiment,
    CleanPost,
    EventReturn,
    FeatureRow,
    MarketObservation,
    SentimentOutput,
)
from musk_sentiment.smoke import run_smoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/posts_synthetic.csv"
CONFIG = ROOT / "configs/project.toml"


def dt(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@pytest.mark.parametrize(
    "value,zone,expected",
    [
        ("2024-07-01T12:00:00-04:00", None, "2024-07-01T16:00:00Z"),
        ("2024-01-01 12:00", "Asia/Hong_Kong", "2024-01-01T04:00:00Z"),
    ],
)
def test_timestamp(value, zone, expected):
    assert timestamp(value, zone) == dt(expected)


@pytest.mark.parametrize(
    "value,zone",
    [
        ("2024-01-01", None),
        ("", None),
        ("2024-03-10 02:30", "America/New_York"),
        ("2024-11-03 01:30", "America/New_York"),
    ],
)
def test_timestamp_ambiguous_missing(value, zone):
    with pytest.raises(ValueError):
        timestamp(value, zone)


def test_import_and_raw_immutability(tmp_path):
    posts, report = import_posts(
        FIXTURE, tmp_path / "out", tmp_path / "raw", "fixture", synthetic=True
    )
    assert len(posts) == 2
    assert posts[1].likes is None
    assert report["counts"] == {
        "input_rows": 6,
        "duplicate_rows": 1,
        "invalid_rows": 1,
        "reply_or_repost": 1,
        "unknown_original_status": 1,
        "clean_rows": 2,
    }
    path = Path(report["raw_snapshot"])
    before = path.stat().st_mtime_ns
    import_posts(FIXTURE, tmp_path / "out", tmp_path / "raw", "fixture", synthetic=True)
    assert path.read_bytes() == FIXTURE.read_bytes()
    assert path.stat().st_mtime_ns == before


def test_conflicting_ids_excluded(tmp_path):
    path = tmp_path / "conflict.csv"
    path.write_text(
        "post_id,text,created_at,author,is_reply,is_repost\n"
        "123,one,2024-01-01T00:00Z,elonmusk,false,false\n"
        "123,two,2024-01-01T00:00Z,elonmusk,false,false\n"
    )
    posts, report = import_posts(path, tmp_path / "out", tmp_path / "raw", "fixture")
    assert posts == []
    assert report["counts"]["conflicting_ids_excluded"] == 1


def test_missing_required_columns(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("text\nhello\n")
    with pytest.raises(ValueError, match="Missing CSV columns"):
        import_posts(path, tmp_path / "out", tmp_path / "raw", "fixture")


@pytest.mark.parametrize(
    "posted,expected",
    [
        ("2024-07-03T18:00:00Z", "2024-07-05T13:30:00Z"),  # early close + holiday
        ("2024-07-06T12:00:00Z", "2024-07-08T13:30:00Z"),  # weekend
        ("2024-07-05T12:00:00Z", "2024-07-05T13:30:00Z"),  # pre-market
        ("2024-07-05T15:00:00Z", "2024-07-05T15:00:00Z"),  # during session
        ("2024-07-05T20:00:00Z", "2024-07-08T13:30:00Z"),  # exactly close
        ("2024-03-08T21:01:00Z", "2024-03-11T13:30:00Z"),  # DST change
    ],
)
def test_exchange_alignment(posted, expected):
    assert next_trading_time(dt(posted), "XNYS") == dt(expected)


def test_crypto_weekend_and_equity_holiday():
    posted = dt("2024-07-06T12:00:00Z")
    assert next_trading_time(posted, "24/7") == posted
    with pytest.raises(ValueError, match="not a"):
        session_bounds("2024-07-04", "XNYS")
    assert session_bounds("2024-07-03", "XNYS")[1] == dt("2024-07-03T17:00:00Z")


def test_returns():
    assert simple_return(100, 110) == pytest.approx(0.1)
    assert benchmark_adjusted(0.1, 0.02) == pytest.approx(0.08)
    for price in (0, -1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            simple_return(price, 100)


def test_market_missing_and_daily_boundary():
    asset = load_config(CONFIG)["assets"][0]
    frame = pd.DataFrame(
        {
            "Open": [100, 100],
            "High": [102, 102],
            "Low": [99, 99],
            "Close": [101, float("nan")],
            "Volume": [50, 50],
        },
        index=pd.to_datetime(["2024-07-03", "2024-07-05"]),
    )
    bars, rejected = normalize_market(frame, asset, "1d", dt("2024-07-10T00:00Z"))
    assert len(bars) == len(rejected) == 1
    assert bars[0].bar_end == dt("2024-07-03T17:00Z")
    assert bars[0].adjusted
    bars, _ = normalize_market(frame.iloc[:1], asset, "1d", dt("2024-07-03T16:00Z"))
    assert not bars


def test_partial_hour_at_close():
    asset = load_config(CONFIG)["assets"][0]
    frame = pd.DataFrame(
        {"Open": [100], "High": [102], "Low": [99], "Close": [101], "Volume": [50]},
        index=pd.to_datetime(["2024-07-03T16:30Z"]),
    )
    bars, rejected = normalize_market(frame, asset, "1h", dt("2024-07-04T00:00Z"))
    assert not rejected
    assert bars[0].bar_end == dt("2024-07-03T17:00Z")


def test_yahoo_empty_is_explicit_failure(tmp_path, monkeypatch):
    class FakeTicker:
        def history(self, **kwargs):
            assert kwargs["interval"] == "1h"
            assert kwargs["auto_adjust"] is True
            return pd.DataFrame()

    monkeypatch.setattr("musk_sentiment.data.market.yf.Ticker", lambda _: FakeTicker())
    asset = load_config(CONFIG)["assets"][0]
    with pytest.raises(MarketDataUnavailable):
        collect_market(asset, "2021-01-01", "2021-02-01", "1h", tmp_path, tmp_path / "raw")
    assert json.loads((tmp_path / "TSLA_1h_quality.json").read_text())["status"] == "failed"


def test_nlp_cache_mapping_retries(tmp_path):
    posts, _ = import_posts(
        FIXTURE, tmp_path / "posts", tmp_path / "raw", "fixture", synthetic=True
    )
    assets = load_config(CONFIG)["assets"]

    class CountingProvider(SyntheticProvider):
        calls = 0

        def generate(self, system, user):
            self.calls += 1
            if self.calls == 1:
                return "invalid JSON"
            return super().generate(system, user)

    provider = CountingProvider()
    record = infer(posts[0], assets, provider, tmp_path / "cache")
    assert record.synthetic and provider.calls == 2
    assert infer(posts[0], assets, provider, tmp_path / "cache") == record
    assert provider.calls == 2
    provider.model = "changed-v2"
    assert infer(posts[0], assets, provider, tmp_path / "cache").cache_key != record.cache_key
    assert provider.calls == 3


def test_nlp_reject_unknown_asset(tmp_path):
    posts, _ = import_posts(FIXTURE, tmp_path / "posts", tmp_path / "raw", "fixture")
    assets = load_config(CONFIG)["assets"]

    class WrongProvider(SyntheticProvider):
        def generate(self, system, user):
            return super().generate(system, user).replace('"TSLA"', '"UNKNOWN"')

    with pytest.raises(RuntimeError, match="after 1 attempts"):
        infer(posts[0], assets, WrongProvider(), tmp_path / "cache", attempts=1)
    assert not list((tmp_path / "cache").glob("*.json"))


def test_schema_validation():
    with pytest.raises(ValidationError):
        AssetSentiment(ticker="TSLA", sentiment="bullish", sentiment_score=-0.5, confidence=0.8)
    with pytest.raises(ValidationError):
        SentimentOutput(
            post_id="x",
            market_relevant=False,
            topics=[],
            impact_horizon="unknown",
            ambiguity="none",
            assets=[
                {"ticker": "TSLA", "sentiment": "neutral", "sentiment_score": 0, "confidence": 0.5}
            ],
        )
    with pytest.raises(ValidationError):
        CleanPost(
            post_id="x",
            text="x",
            created_at=datetime(2024, 1, 1),
            author="elonmusk",
            source="test",
            normalized_text="x",
        )


def feature(event_id, prediction, end):
    return FeatureRow(
        event_id=event_id,
        ticker="TSLA",
        prediction_at=dt(prediction),
        features_available_at=dt(prediction),
        label_end=dt(end),
        features={"sentiment": 0},
        target=0.01,
        synthetic=True,
    )


def test_leakage_and_purged_split():
    early = feature("early", "2024-01-01T00:00Z", "2024-01-02T00:00Z")
    overlap = feature("overlap", "2024-01-02T00:00Z", "2024-01-04T00:00Z")
    later = feature("test", "2024-01-03T00:00Z", "2024-01-04T00:00Z")
    train, test = purged_split([later, overlap, early], dt("2024-01-03T00:00Z"))
    assert train == [early] and test == [later]
    with pytest.raises(ValidationError):
        FeatureRow(**{**early.model_dump(), "features_available_at": dt("2024-01-02T00:00Z")})
    with pytest.raises(ValidationError):
        EventReturn(
            event_id="x",
            ticker="TSLA",
            prediction_at=early.prediction_at,
            baseline_at=early.label_end,
            outcome_at=later.label_end,
            interval="1d",
            horizon_bars=1,
            raw_return=0.1,
            synthetic=True,
        )


def test_smoke_reproducible(tmp_path):
    first = run_smoke(FIXTURE, CONFIG, tmp_path)
    records = (tmp_path / "final" / "returns.json").read_bytes()
    second = run_smoke(FIXTURE, CONFIG, tmp_path)
    assert first == second
    assert (tmp_path / "final" / "returns.json").read_bytes() == records
    assert first["synthetic"] and first["events"] == 2
    assert first["train_rows"] == first["test_rows"] == 1
    for record in json.loads((tmp_path / "processed" / "market_synthetic.json").read_text()):
        assert MarketObservation.model_validate(record).synthetic


def test_csv_column_mapping_and_long_id(tmp_path):
    path = tmp_path / "mapped.csv"
    path.write_text(
        "id,tweet,date,user,reply,repost\n"
        "18446744073709551615,hello,2024-01-01 08:00,elonmusk,0,0\n"
    )
    posts, _ = import_posts(
        path,
        tmp_path / "out",
        tmp_path / "raw",
        "fixture",
        {
            "post_id": "id",
            "text": "tweet",
            "created_at": "date",
            "author": "user",
            "is_reply": "reply",
            "is_repost": "repost",
        },
        source_timezone="Asia/Hong_Kong",
    )
    assert posts[0].post_id == "18446744073709551615"
    assert posts[0].created_at == dt("2024-01-01T00:00Z")


def test_ollama_adapter_contract(monkeypatch):
    import httpx

    from musk_sentiment.nlp.provider import OllamaProvider

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "test:latest", "digest": "abc"}]})
        if request.url.path == "/api/show":
            return httpx.Response(200, json={})
        body = json.loads(request.content)
        assert body["stream"] is False
        assert body["options"]["temperature"] == 0
        assert body["format"]["title"] == "SentimentOutput"
        return httpx.Response(200, json={"message": {"content": "{}"}})

    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    provider = OllamaProvider("test")
    assert provider.model == "test:latest@abc"
    assert provider.generate("system", "user") == "{}"


def test_ollama_rejects_remote_model(monkeypatch):
    import httpx

    from musk_sentiment.nlp.provider import OllamaProvider

    def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "test:latest", "digest": "abc"}]})
        return httpx.Response(200, json={"remote_host": "cloud.invalid"})

    original = httpx.Client
    monkeypatch.setattr(
        httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs)
    )
    with pytest.raises(ValueError, match="Cloud-backed"):
        OllamaProvider("test")


def test_yahoo_success_preserves_response(tmp_path, monkeypatch):
    frame = pd.DataFrame(
        {"Open": [100], "High": [102], "Low": [99], "Close": [101], "Volume": [50]},
        index=pd.to_datetime(["2024-07-03"]),
    )

    class FakeTicker:
        def history(self, **kwargs):
            return frame

    monkeypatch.setattr("musk_sentiment.data.market.yf.Ticker", lambda _: FakeTicker())
    asset = load_config(CONFIG)["assets"][0]
    report = collect_market(asset, "2024-07-03", "2024-07-04", "1d", tmp_path, tmp_path / "raw")
    assert report["status"] == "ok" and report["rows"] == 1
    assert Path(report["raw_snapshot"]).read_text() == frame.to_csv()
    records = json.loads((tmp_path / "TSLA_1d.json").read_text())
    assert MarketObservation.model_validate(records[0]).synthetic is False


def test_cli_error_and_offline_smoke(tmp_path, capsys):
    from musk_sentiment.cli import main

    assert (
        main(
            ["smoke", "--fixture", str(FIXTURE), "--config", str(CONFIG), "--output", str(tmp_path)]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["synthetic"]
    assert main(["collect-market", "--config", str(CONFIG), "--tickers", "UNKNOWN"]) == 1
