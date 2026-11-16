import csv
import json
from datetime import timedelta
from pathlib import Path

import httpx
import numpy as np
import pytest

from musk_sentiment.analysis.study import build_study, describe_study
from musk_sentiment.config import load_config
from musk_sentiment.data.alpaca import aggregate_sip, collect_alpaca, session_grid
from musk_sentiment.data.corpus import import_kaggle, prepare_corpus, read_posts
from musk_sentiment.data.local_market import daily_crypto, import_crypto_csv
from musk_sentiment.evaluation.annotations import sample_annotations, score_annotations
from musk_sentiment.models.research import chronological_split, evaluate_models
from musk_sentiment.nlp.pipeline import infer
from musk_sentiment.nlp.provider import SyntheticProvider
from musk_sentiment.schemas import Asset, CleanPost, MarketObservation, NLPRecord, SentimentOutput
from musk_sentiment.utils.io import save_records

CONFIG = Path("configs/project.toml")


def dt(value):
    from datetime import datetime

    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def post(pid="18446744073709551615", when="2020-01-03T14:45:00Z"):
    return CleanPost(
        post_id=pid,
        text="Tesla production",
        normalized_text="Tesla production",
        created_at=dt(when),
        author="elonmusk",
        source="fixture",
        synthetic=True,
    )


def test_kaggle_unknown_flags_author_and_ids(tmp_path):
    path = tmp_path / "raw.csv"
    path.write_text(
        "id,twitterUrl,fullText,createdAt,isReply,isRetweet,likeCount\n"
        "18446744073709551615,https://twitter.com/elonmusk/status/18446744073709551615,hello,2020-01-01T00:00Z,False,False,1\n"
        "2,https://twitter.com/elonmusk/status/2,unknown,2020-01-01T00:00Z,,False,1\n"
        "3,https://twitter.com/someone/status/3,other,2020-01-01T00:00Z,False,False,1\n"
        "4,https://twitter.com/elonmusk/status/5,mismatch,2020-01-01T00:00Z,False,False,1\n"
    )
    report = import_kaggle(path, tmp_path / "out", tmp_path / "raw")
    assert report["counts"]["clean_rows"] == 1
    assert report["counts"]["unknown_original_status"] == 1
    assert report["counts"]["other_author"] == 1
    assert len(report["source_identity_rejections"]) == 1
    assert read_posts(tmp_path / "out/posts.json")[0].post_id == "18446744073709551615"


def test_window_exclusive_and_missing_months(tmp_path):
    p = tmp_path / "posts.json"
    save_records(
        p,
        [
            post("1", "2020-01-01T00:00:00Z"),
            post("2", "2021-12-31T23:59:59Z"),
            post("3", "2022-01-01T00:00:00Z"),
        ],
    )
    report = prepare_corpus(p, tmp_path / "study", "2020-01-01", "2022-01-01")
    assert report["rows"] == 2 and len(report["empty_months"]) == 22
    bad = json.loads(p.read_text())
    bad[0]["post_id"] = 18446744073709551615
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="strings"):
        read_posts(p)


def halves(asset, day="2020-07-02", end="2020-07-03"):
    return [
        dict(t=a.isoformat(), o=100, h=103, l=99, c=102, v=10)
        for a, b in session_grid(asset, day, end, "30Min")
    ]


def test_sip_aggregation_missing_half_and_premarket():
    asset = load_config(CONFIG)["assets"][0]
    inputs = halves(asset)
    # 09:00 New York must not inflate first regular bar's price/volume.
    inputs.insert(0, dict(t="2020-07-02T13:00:00Z", o=999, h=999, l=999, c=999, v=999))
    bars, q = aggregate_sip(inputs, asset, "2020-07-02", "2020-07-03", "1h")
    assert len(bars) == 7 and not q["missing_starts"]
    assert bars[0].bar_start == dt("2020-07-02T13:30:00Z") and bars[0].volume == 20
    assert bars[-1].bar_end - bars[-1].bar_start == timedelta(minutes=30)
    bars, q = aggregate_sip(inputs[2:], asset, "2020-07-02", "2020-07-03", "1h")
    assert len(bars) == 6 and len(q["missing_starts"]) == 1
    daily, q = aggregate_sip(inputs[2:], asset, "2020-07-02", "2020-07-03", "1d")
    assert not daily


def test_alpaca_pagination_and_secret_not_saved(tmp_path, monkeypatch):
    asset = load_config(CONFIG)["assets"][0]
    inputs = halves(asset)
    calls = []
    monkeypatch.setenv("APCA_API_KEY_ID", "secret-key")
    monkeypatch.setenv("APCA_API_SECRET_KEY", "secret-value")
    monkeypatch.setattr("musk_sentiment.data.alpaca.time.sleep", lambda _: None)

    def handler(request):
        calls.append(request)
        assert request.url.params["feed"] == "sip" and request.url.params["timeframe"] == "30Min"
        assert request.url.params["end"].startswith("2020-07-02T23:59:59.999999")
        if "page_token" not in request.url.params:
            return httpx.Response(
                200, json={"bars": {"TSLA": inputs[:5]}, "next_page_token": "next"}
            )
        return httpx.Response(200, json={"bars": {"TSLA": inputs[5:]}, "next_page_token": None})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        report = collect_alpaca(
            asset, "2020-07-02", "2020-07-03", "1h", tmp_path / "out", tmp_path / "raw", client
        )
    assert report["rows"] == 7 and len(calls) == 2 and report["status"] == "complete"
    assert all("secret-value" not in p.read_text() for p in tmp_path.rglob("*.json"))


def crypto_asset(ticker="ETH-USD", benchmark="BTC-USD"):
    return Asset(ticker=ticker, asset_class="crypto", calendar="24/7", benchmark=benchmark)


def test_crypto_usdt_rejected_and_complete_day_only(tmp_path):
    p = tmp_path / "prices.csv"
    p.write_text(
        "ticker,quote_currency,timestamp,open,high,low,close,volume\n"
        "ETH-USD,USDT,1577836800,1,1,1,1,1\n"
    )
    with pytest.raises(ValueError, match="USDT"):
        import_crypto_csv(
            p,
            crypto_asset(),
            "1h",
            "2020-01-01",
            "2020-01-02",
            "fixture",
            tmp_path,
            tmp_path / "raw",
        )
    p.write_text(p.read_text().replace(",USDT,", ",USD,"))
    report = import_crypto_csv(
        p, crypto_asset(), "1h", "2020-01-01", "2020-01-02", "fixture", tmp_path, tmp_path / "raw"
    )
    assert len(report["missing_starts"]) == 23
    bars = [
        MarketObservation.model_validate(v)
        for v in json.loads((tmp_path / "ETH-USD_1h.json").read_text())
    ]
    assert daily_crypto(bars) == []


def study_inputs():
    assets = [crypto_asset(), crypto_asset("BTC-USD", "BTC-USD")]
    grid = session_grid(assets[0], "2020-01-01", "2020-01-08", "1h")
    markets = {}
    for asset in assets:
        price = 100.0
        bars = []
        for i, (start, end) in enumerate(grid):
            change = 0.001 * np.sin(i) + 0.0002
            close = price * (1 + change)
            bars.append(
                MarketObservation(
                    ticker=asset.ticker,
                    bar_start=start,
                    bar_end=end,
                    interval="1h",
                    open=price,
                    close=close,
                    high=max(price, close),
                    low=min(price, close),
                    volume=10,
                    adjusted=False,
                    source="fixture",
                    synthetic=True,
                )
            )
            price = close
        markets[asset.ticker] = bars
    posts = [post("1", "2020-01-04T00:30:00Z"), post("2", "2020-01-04T00:30:00Z")]
    records = []
    for p in posts:
        output = SentimentOutput(
            post_id=p.post_id,
            market_relevant=True,
            assets=[
                dict(ticker="ETH-USD", sentiment="bullish", sentiment_score=0.5, confidence=0.6)
            ],
            topics=["adoption"],
            ambiguity="none",
            impact_horizon="unknown",
        )
        records.append(
            NLPRecord(
                output=output,
                provider="fixture",
                model="fixture",
                prompt_version="fixture",
                cache_key="fixture",
                parameters={},
                synthetic=True,
            )
        )
    return posts, records, markets, assets


def test_event_partial_hour_market_model_and_mentions():
    posts, nlp, markets, assets = study_inputs()
    rows, reject = build_study(posts, nlp, markets, assets, "1h", [1, 3], 60, 30)
    assert not reject and len(rows) == 4
    row = rows[0]
    assert row.baseline_at == dt("2020-01-04T00:00:00Z")
    assert row.entry_at == dt("2020-01-04T01:00:00Z")
    assert row.outcome_at == dt("2020-01-04T01:00:00Z")
    assert row.label_end == dt("2020-01-04T02:00:00Z")
    assert row.beta == pytest.approx(1) and row.market_model_car == pytest.approx(0, abs=1e-12)
    assert [r.mention_index for r in rows] == [1, 1, 2, 2]
    assert rows[2].topic_mention_indices == {"adoption": 2}
    assert all(r.synthetic for r in rows)


def test_missing_event_bar_is_not_skipped_to_later_bar():
    posts, nlp, markets, assets = study_inputs()
    markets["ETH-USD"] = [
        b for b in markets["ETH-USD"] if b.bar_start != dt("2020-01-04T01:00:00Z")
    ]
    rows, reject = build_study(posts, nlp, markets, assets, "1h", [1], 60, 30)
    assert not rows and len(reject) == 2
    assert all("Missing required" in r["reason"] for r in reject)


def test_no_nlp_partial_corpus_or_unknown_tickers():
    posts, nlp, markets, assets = study_inputs()
    with pytest.raises(ValueError, match="exactly one"):
        build_study(posts, nlp[:1], markets, assets, "1h", [1])


def test_annotation_sample_string_ids_locked(tmp_path):
    sample = tmp_path / "labels.csv"
    sample_annotations([post()], load_config(CONFIG)["assets"], sample, 2)
    with sample.open() as f:
        r = list(csv.DictReader(f))
    assert r[0]["post_id"] == "18446744073709551615"
    with pytest.raises(ValueError, match="already exists"):
        sample_annotations([post()], load_config(CONFIG)["assets"], sample, 2)


def test_gold_sentiment_counts_missing_asset_as_wrong(tmp_path):
    gold = tmp_path / "gold.csv"
    pred = tmp_path / "pred.json"
    gold.write_text(
        "post_id,split,annotator_id,market_relevant,ticker,sentiment,sentiment_score\n"
        "18446744073709551615,test,human,true,TSLA,bullish,0.5\n"
    )
    record = infer(post(), load_config(CONFIG)["assets"], SyntheticProvider(), tmp_path / "cache")
    record.synthetic = False
    record.output.assets = []
    save_records(pred, [record])
    result = score_annotations(gold, pred)
    assert result["gold_asset_sentiment_accuracy"] == 0
    gold.write_text(gold.read_text().replace("18446744073709551615", "18446744073709551616"))
    with pytest.raises(ValueError, match="exact-ID"):
        score_annotations(gold, pred)


def test_chronological_overlap_purge():
    posts, nlp, markets, assets = study_inputs()
    rows, _ = build_study(posts, nlp, markets, assets, "1h", [3], 60, 30)
    early = rows[0].model_copy(
        update={
            "event_id": "early",
            "posted_at": dt("2020-01-03T00:00Z"),
            "baseline_at": dt("2020-01-02T23:00Z"),
            "entry_at": dt("2020-01-03T00:00Z"),
            "outcome_at": dt("2020-01-03T04:00Z"),
            "label_end": dt("2020-01-03T04:00Z"),
        }
    )
    overlap = rows[0].model_copy(
        update={"event_id": "overlap", "posted_at": dt("2020-01-03T23:59Z")}
    )
    train, test = chronological_split([early, overlap, rows[1]], "2020-01-04")
    assert train == [early] and test == [rows[1]]


def test_models_and_descriptives_deterministic():
    posts, nlp, markets, assets = study_inputs()
    template = build_study(posts, nlp, markets, assets, "1h", [1], 60, 30)[0][0]
    rows = []
    for i in range(50):
        start = dt("2020-01-01T12:00Z") + timedelta(days=i * 12)
        rows.append(
            template.model_copy(
                update={
                    "event_id": str(i),
                    "post_id": str(i),
                    "posted_at": start,
                    "baseline_at": start - timedelta(hours=1),
                    "outcome_at": start + timedelta(hours=1),
                    "entry_at": start,
                    "label_end": start + timedelta(hours=2),
                    "predictive_return": 0.001 * np.sin(i),
                    "features": {"lagged_return": 0.001 * np.cos(i), "volatility": 0.001},
                }
            )
        )
    result = evaluate_models(rows, "2021-01-01", "2021-04-01")
    assert len(result["scores"]) == 24
    assert all(np.isfinite(r["predicted"]) for r in result["predictions"])
    report = describe_study(rows, repetitions=20)
    assert report and any(r["cluster_bootstrap_95ci"] is not None for r in report)


def test_research_orchestration_and_figures(tmp_path, monkeypatch):
    from musk_sentiment.analysis.run import plot_research, run_research

    posts, nlp, markets, assets = study_inputs()
    save_records(tmp_path / "posts.json", posts)
    save_records(tmp_path / "nlp.json", nlp)
    for ticker, bars in markets.items():
        save_records(tmp_path / "market" / f"{ticker}_1h.json", bars)
        save_records(tmp_path / "market" / f"{ticker}_1d.json", daily_crypto(bars))
    config = tmp_path / "config.toml"
    config.write_text(
        CONFIG.read_text()
        .replace("estimation_bars = 120", "estimation_bars = 60")
        .replace("min_estimation_bars = 60", "min_estimation_bars = 30")
    )
    result = run_research(
        tmp_path / "posts.json",
        tmp_path / "nlp.json",
        tmp_path / "market",
        config,
        tmp_path / "result",
        synthetic=True,
    )
    assert result["synthetic"] and result["events"] > 0 and result["missing_market_files"]
    assert (tmp_path / "result/isolated_sensitivity.json").exists()
    monkeypatch.setenv("MPLCONFIGDIR", str(tmp_path / "matplotlib"))
    figures = plot_research(tmp_path / "result")["figures"]
    assert figures and Path(figures[0]).read_bytes().startswith(b"\x89PNG")
    with pytest.raises(ValueError, match="synthetic"):
        run_research(
            tmp_path / "posts.json",
            tmp_path / "nlp.json",
            tmp_path / "market",
            config,
            tmp_path / "invalid",
            synthetic=False,
        )


def test_duplicate_half_invalidates_aggregate():
    asset = load_config(CONFIG)["assets"][0]
    inputs = halves(asset)
    bars, report = aggregate_sip(inputs + [inputs[0]], asset, "2020-07-02", "2020-07-03", "1h")
    assert len(bars) == 6 and len(report["missing_starts"]) == 1
    assert "Duplicate" in report["rejected"][0]["reason"]


def test_equity_holiday_event_uses_next_session_open(tmp_path):
    assets = [a for a in load_config(CONFIG)["assets"] if a.ticker in {"TSLA", "SPY"}]
    markets = {}
    for asset in assets:
        bars = []
        for i, (opening, closing) in enumerate(
            session_grid(asset, "2020-06-29", "2020-07-09", "1h")
        ):
            bars.append(
                MarketObservation(
                    ticker=asset.ticker,
                    bar_start=opening,
                    bar_end=closing,
                    interval="1h",
                    open=100 + i,
                    high=102 + i,
                    low=99 + i,
                    close=101 + i,
                    volume=10,
                    source="fixture",
                    adjusted=True,
                    synthetic=True,
                )
            )
        markets[asset.ticker] = bars
    p = post(when="2020-07-03T16:00:00Z")  # observed Independence Day holiday
    record = infer(p, assets, SyntheticProvider(), tmp_path / "cache")
    rows, rejections = build_study([p], [record], markets, assets, "1h", [1], 10, 3)
    assert not rejections
    assert rows[0].baseline_at == dt("2020-07-02T20:00:00Z")
    assert rows[0].entry_at == dt("2020-07-06T13:30:00Z")
    assert rows[0].label_end == dt("2020-07-06T14:30:00Z")


def test_empirical_research_rejects_old_nlp_without_input_fingerprint(tmp_path):
    from musk_sentiment.analysis.run import run_research

    p = post().model_copy(update={"synthetic": False})
    save_records(tmp_path / "posts.json", [p])
    record = infer(p, load_config(CONFIG)["assets"], SyntheticProvider(), tmp_path / "cache")
    record.synthetic = False
    record.input_sha256 = None
    save_records(tmp_path / "nlp.json", [record])
    with pytest.raises(ValueError, match="fingerprint"):
        run_research(
            tmp_path / "posts.json",
            tmp_path / "nlp.json",
            tmp_path / "market",
            CONFIG,
            tmp_path / "out",
        )
