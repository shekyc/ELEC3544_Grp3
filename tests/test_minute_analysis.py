"""Offline boundary tests for minute timing, provenance, missing data and past-only references."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from musk_sentiment.analysis.minute import (
    MinuteStore,
    SessionClock,
    build_minute_events,
    ceil_minute,
    clusters,
    measurements,
    relative_activity,
)
from musk_sentiment.data.minute import publish_minutes
from musk_sentiment.models.minute import split_minute_rows
from musk_sentiment.schemas import (
    Asset,
    CleanPost,
    MinuteBar,
    MinuteEvent,
    NLPRecord,
    SentimentOutput,
)


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def bar(at, price=100, volume=10, count=2):
    return MinuteBar(t=at, o=price, h=price, l=price, c=price, v=volume, n=count)


@pytest.fixture
def clock():
    return SessionClock("2019-12-01", "2022-01-08")


def test_dst_and_closed_market_next_open(clock):
    assert clock.classify(dt("2020-03-06T14:30:01Z"))[0] == "regular"
    assert clock.classify(dt("2020-03-09T13:30:01Z"))[0] == "regular"
    assert clock.classify(dt("2021-11-05T13:30:01Z"))[0] == "regular"
    assert clock.classify(dt("2021-11-08T14:30:01Z"))[0] == "regular"
    cohort, entry, _ = clock.classify(dt("2021-03-13T15:00:00Z"))
    assert cohort == "next_opening" and entry == dt("2021-03-15T13:30:00Z")
    assert clock.classify(dt("2020-01-01T06:50:06Z"))[1] == dt("2020-01-02T14:30:00Z")


def test_extended_hours_and_early_close(clock):
    assert clock.classify(dt("2020-01-07T09:47:04Z"))[0] == "extended"
    assert clock.classify(dt("2021-12-23T00:35:39Z"))[0] == "extended"
    assert clock.classify(dt("2020-11-27T17:59:30Z"))[2] == dt("2020-11-27T18:00:00Z")
    assert clock.classify(dt("2020-11-27T18:00:00Z"))[0] == "extended"
    assert clock.classify(dt("2020-01-07T01:00:00Z"))[0] == "next_opening"


def test_next_full_minute_and_exact_boundary():
    assert ceil_minute(dt("2020-01-01T12:00:01Z")) == dt("2020-01-01T12:01:00Z")
    assert ceil_minute(dt("2020-01-01T12:00:00Z")) == dt("2020-01-01T12:00:00Z")
    with pytest.raises(ValueError, match="Naive"):
        bar(datetime(2020, 1, 1))
    with pytest.raises(ValueError, match="minute-aligned"):
        bar(dt("2020-01-01T00:00:01Z"))


def test_no_gap_fill_and_immutable_processed_files(tmp_path):
    rows = [
        bar(dt("2020-01-01T00:00:00Z")).model_dump(),
        bar(dt("2020-01-01T00:02:00Z")).model_dump(),
    ]
    publish_minutes(rows, "X", tmp_path, {"provider": "test"})
    store = MinuteStore(tmp_path)
    with pytest.raises(ValueError, match="Missing required"):
        store.window("X", dt("2020-01-01T00:00:00Z"), 3)
    with pytest.raises(ValueError, match="Duplicate minute"):
        publish_minutes(rows + rows, "X", tmp_path, {"provider": "test"})
    rows[0]["v"] = 999
    with pytest.raises(ValueError, match="Refusing to replace"):
        publish_minutes(rows, "X", tmp_path, {"provider": "test"})


def test_measurements_units_and_cross_minute_price_change():
    a = bar(dt("2020-01-01T00:00:00Z"), 100, 7, 2)
    b = bar(dt("2020-01-01T00:01:00Z"), 110, 3, 4)
    result = measurements([a, b])
    assert result["forward_return"] == pytest.approx(0.1)
    assert result["volume"] == 10 and result["trade_count"] == 6
    import math

    assert result["realized_volatility"] == pytest.approx(math.log(1.1))


def test_past_only_matched_local_time_reference_across_dst(clock):
    calls = []

    class Store:
        def window(self, ticker, start, minutes):
            calls.append(start)
            return [bar(start + timedelta(minutes=i)) for i in range(minutes)]

    entry = dt("2020-03-10T14:00:00Z")  # 10:00 New York, after DST transition
    result = relative_activity(
        Store(),
        clock,
        "X",
        entry,
        entry - timedelta(seconds=10),
        "regular",
        5,
        {"baseline_sessions": 3, "minimum_baseline_windows": 3},
    )
    assert result["reference_volume"] == 50 and result["reference_trade_count"] == 10
    assert dt("2020-03-06T15:00:00Z") in calls  # same 10:00 local before DST
    assert all(start + timedelta(minutes=5) < entry for start in calls)


def event_fixture():
    post = CleanPost(
        post_id="1",
        text="x",
        normalized_text="x",
        created_at=dt("2020-01-03T15:00:30Z"),
        author="elonmusk",
        source="fixture",
    )
    asset = Asset(ticker="X", asset_class="stock", calendar="XNYS", benchmark="X", aliases=[])
    output = SentimentOutput(
        post_id="1",
        market_relevant=True,
        assets=[dict(ticker="X", sentiment="bullish", sentiment_score=0.5, confidence=0.8)],
        topics=[],
        impact_horizon="unknown",
        ambiguity="none",
    )
    nlp = NLPRecord(
        output=output,
        provider="test",
        model="test",
        prompt_version="test",
        cache_key="test",
        parameters={},
        synthetic=False,
    )
    settings = {
        "market_start": "2019-12-01",
        "market_end": "2022-01-08",
        "horizons_minutes": [5, 15, 30],
        "baseline_sessions": 20,
        "minimum_baseline_windows": 10,
    }
    return post, asset, nlp, settings


def test_features_stop_before_post_and_cross_boundary_rejection():
    post, asset, nlp, settings = event_fixture()

    class Store:
        def bar(self, ticker, at):
            return bar(at)

        def window(self, ticker, start, minutes):
            return [
                bar(start + timedelta(minutes=i), volume=1000 if start > post.created_at else 10)
                for i in range(minutes)
            ]

    rows, rejected, _ = build_minute_events([post], [nlp], [asset], Store(), settings)
    assert len(rows) == 3 and not rejected
    assert rows[0].entry_at == dt("2020-01-03T15:01:00Z")
    assert rows[0].features_end_at == dt("2020-01-03T15:00:00Z")
    import math

    assert rows[0].features["log_volume"] == pytest.approx(math.log1p(50))
    assert rows[0].volume == 5000
    invalid = rows[0].model_dump()
    invalid["features_end_at"] = rows[0].end_at
    with pytest.raises(ValueError, match="Future market"):
        MinuteEvent.model_validate(invalid)
    post.created_at = dt("2020-01-03T20:58:30Z")
    rows, rejected, _ = build_minute_events([post], [nlp], [asset], Store(), settings)
    assert not rows and len(rejected) == 3
    assert all(r["reason"] == "Window crosses session boundary" for r in rejected)


def test_overlap_cluster_purging_at_chronological_boundary():
    cutoff = datetime(2021, 7, 1, tzinfo=UTC)
    rows = [
        SimpleNamespace(
            event_id="a",
            posted_at=cutoff - timedelta(days=1),
            entry_at=cutoff,
            end_at=cutoff + timedelta(minutes=5),
        ),
        SimpleNamespace(
            event_id="b", posted_at=cutoff, entry_at=cutoff, end_at=cutoff + timedelta(minutes=5)
        ),
        SimpleNamespace(
            event_id="c",
            posted_at=cutoff - timedelta(days=2),
            entry_at=cutoff - timedelta(days=2),
            end_at=cutoff - timedelta(days=2) + timedelta(minutes=5),
        ),
    ]
    assert clusters(rows)["a"] == clusters(rows)["b"]
    train, test = split_minute_rows(rows, cutoff)
    assert [r.event_id for r in train] == ["c"] and [r.event_id for r in test] == ["b"]


def test_day_clustering_does_not_count_same_day_posts_as_independent():
    from musk_sentiment.analysis.minute import describe_minutes

    rows = []
    for i in range(6):
        entry = dt("2020-01-02T14:40:00Z") + timedelta(minutes=i * 10)
        rows.append(
            SimpleNamespace(
                event_id=str(i),
                ticker="TSLA",
                cohort="regular",
                horizon_minutes=5,
                entry_at=entry,
                end_at=entry + timedelta(minutes=5),
                forward_return=0.01,
                benchmark_adjusted_return=0.005,
                relative_volume=2.0,
                relative_trade_count=2.0,
                relative_volatility=2.0,
                sentiment_score=0.5,
            )
        )
    settings = {"seed": 1, "bootstrap_repetitions": 20}
    separate = describe_minutes(rows, settings)
    combined = describe_minutes(rows, settings, "day")
    assert separate["summaries"][0]["clusters"] == 6
    assert combined["summaries"][0]["clusters"] == 1
    assert combined["summaries"][0]["sign_test_p"] is None
    assert combined["summaries"][0]["cluster_bootstrap_95ci"] is None


def test_minute_pagination_resume_and_no_credentials_in_snapshots(tmp_path, monkeypatch):
    import json

    import httpx

    from musk_sentiment.data.minute import collect_stock_minutes

    calls = []
    monkeypatch.setenv("APCA_API_KEY_ID", "private-key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "private-secret")
    monkeypatch.setattr("musk_sentiment.data.minute.time.sleep", lambda _: None)
    original = httpx.Client

    def handler(request):
        calls.append(dict(request.url.params))
        second = "page_token" in request.url.params
        payload = bar(dt("2020-01-02T15:01:00Z" if second else "2020-01-02T15:00:00Z")).model_dump(
            mode="json", exclude={"schema_version", "vw"}
        )
        return httpx.Response(
            200, json={"bars": {"TSLA": [payload]}, "next_page_token": None if second else "next"}
        )

    monkeypatch.setattr(
        "musk_sentiment.data.minute.httpx.Client",
        lambda **kw: original(transport=httpx.MockTransport(handler), **kw),
    )
    args = ("TSLA", "2020-01-01", "2020-01-03", tmp_path / "out", tmp_path / "raw")
    report = collect_stock_minutes(*args)
    assert report["rows"] == 2 and len(calls) == 2
    assert calls[0]["timeframe"] == "1Min" and calls[0]["feed"] == "sip"
    assert calls[1]["page_token"] == "next"
    collect_stock_minutes(*args)
    assert len(calls) == 2  # raw checkpoint replay does not issue new requests
    for p in tmp_path.rglob("*.json"):
        assert "private-key" not in p.read_text() and "private-secret" not in p.read_text()
    day = tmp_path / "out/TSLA/2020-01-02.json"
    data = json.loads(day.read_text())
    data[0]["v"] = 999
    day.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="hash mismatch"):
        MinuteStore(tmp_path / "out").window("TSLA", dt("2020-01-02T15:00:00Z"), 1)


def test_holdout_mentions_continue_instead_of_resetting():
    post, asset, nlp, settings = event_fixture()

    class Store:
        def bar(self, ticker, at):
            return bar(at)

        def window(self, ticker, start, minutes):
            return [bar(start + timedelta(minutes=i)) for i in range(minutes)]

    rows, _, _ = build_minute_events(
        [post], [nlp], [asset], Store(), settings, prior_mentions={"X": 23}
    )
    assert len(rows) == 3
    assert {r.mention_index for r in rows} == {24}
