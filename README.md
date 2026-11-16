# ELEC3544 — Musk sentiment and market reactions

The study retains stocks, sector/market ETFs and cryptocurrencies, financial sentiment and topics,
first/subsequent observed mentions, event studies and traditional predictive models. The approved
post window is **2020-01-01 through 2021-12-31 UTC**. End dates in this project are exclusive.

Branch `sheky/merge` integrates selected work from `tansy` and `cyrus`, not their generated results.
See [integration decisions](docs/INTEGRATION.md) and [current status](docs/PROJECT_STATUS.md).
The code is runnable; empirical NLP accuracy and full market coverage are not yet validated.

## Setup and verification

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-lock.txt
.venv/bin/pip install --no-build-isolation --no-deps -e .
bash scripts/verify.sh
```

`pyproject.toml` keeps research packages optional (`pip install -e '.[dev,research]'`). The lockfile
captures the complete tested environment. Tests are offline; `smoke` contains invented fixtures only.

## 1. Import the original corpus, then select the study period

```bash
.venv/bin/musk-sentiment import-kaggle all_musk_posts.csv
.venv/bin/musk-sentiment prepare-study data/processed/posts_full/posts.json
.venv/bin/musk-sentiment sample-annotations data/processed/study/posts.json
```

Use the original `all_musk_posts.csv`, not the old `_clean.csv` or branch extracts. The dedicated
importer obtains the author from a matching status URL, keeps IDs as strings, excludes replies,
reposts, unknown original-post flags and other authors, and snapshots the exact input bytes.
It does **not** convert missing reply flags to false. No raw data or generated results enter Git.
The existing generic `import-posts` command remains available for other explicitly mapped CSVs.

`data/processed/study/quality.json` reports all 24 monthly counts. Nonempty months are not proof
of corpus completeness. `compare-corpora LEFT RIGHT` audits exact IDs, text matches and normalized
text candidates without repairing IDs or merging files automatically.

## 2. Collect equities and ETFs from Alpaca SIP

Set `APCA_API_KEY_ID` and `APCA_API_SECRET_KEY` in your local shell; do not put secrets in commands
shared with others or commit them. `.env.example` documents variable names; no dotenv auto-loading.

```bash
.venv/bin/musk-sentiment collect-market --provider alpaca --asset-class stock etf --interval 1h
.venv/bin/musk-sentiment collect-market --provider alpaca --asset-class stock etf --interval 1d
```

Defaults request 2019-01-01 through exclusive 2022-02-01 to supply pre-event estimation observations
and late-December outcomes; **post selection remains 2020–2021**. Raw response pages are hashed.
SIP 30-minute bars are aggregated into complete regular-session hourly/daily bars. This avoids
including premarket prices in the first hourly bar. Missing halves invalidate their aggregate.
Split adjustment is explicit. No frequency/provider substitution occurs. `--provider yfinance`
remains an explicit alternative; Yahoo is not a verified 2020–2021 hourly source.

The configurable candidate universe includes TSLA, NVDA, RIVN, AAPL, NIO, SPY, QQQ, XLY, XLK,
BTC-USD, ETH-USD and DOGE-USD. Listing-age gaps (e.g. RIVN) must be distinguished from provider gaps;
the configuration is not a claim that all candidates existed throughout the period.

## 3. Supply audited USD crypto candles

Alpaca's tested equity sample does not establish its 2020 crypto coverage. The verified Binance
archive uses USDT; it is not silently substituted for USD. Until an appropriate USD source is
validated, this is an explicit data blocker, not a reason to drop cryptocurrencies from scope.

CSV columns: `ticker,quote_currency,timestamp,open,high,low,close,volume`.
Use `quote_currency=USD`, timestamp = UTC ISO-8601 or UNIX **seconds**, and a source/version string.

```bash
.venv/bin/musk-sentiment import-crypto path/to/BTC-USD.csv --ticker BTC-USD --interval 1h --source 'provider/version'
.venv/bin/musk-sentiment aggregate-crypto-daily data/processed/market/BTC-USD_1h.json --output data/processed/market/BTC-USD_1d.json
```

Repeat for ETH-USD/DOGE-USD. Daily aggregation requires all 24 UTC hours, with no filling of gaps.

## 4. Label, evaluate and run the local model

`annotations/study_sample.csv` is a deterministic 160-post random/keyword-enriched sample balanced
over eight quarters; the split column reserves dev/test labels. It contains **blank human labels**.
See [annotation rules](docs/ANNOTATION.md). Never show future prices to annotators.

```bash
.venv/bin/musk-sentiment nlp data/processed/study/posts.json --model YOUR_INSTALLED_MODEL
.venv/bin/musk-sentiment score-nlp annotations/study_sample.csv data/processed/nlp/sentiments.json --split dev --output results/nlp_dev.json
.venv/bin/musk-sentiment score-nlp annotations/study_sample.csv data/processed/nlp/sentiments.json --split test --output results/nlp_test.json
```

No model is downloaded automatically. Model digest, prompt version and parameters are recorded;
cache keys invalidate when these or input text change. To compare already-installed models, use
separate `--output` directories and score them on dev; freeze the choice before inspecting test.
The v5 prompt supports every configured asset and avoids mapping SpaceX-only news to TSLA.
A valid JSON response is not evidence of financial sentiment accuracy.

## 5. Run analysis and inspect coverage before interpreting results

```bash
.venv/bin/musk-sentiment research
.venv/bin/musk-sentiment plot-study results/study
```

Outputs include validated events, rejected events with reasons, input hashes, coverage, subgroup
summaries, bootstrap intervals, exploratory sign-flip tests/FDR, isolated-event sensitivity,
chronological model scores and predictions. Missing inputs remain visible; partial diagnostic
outputs must not be presented as completion of the full study. All-synthetic runs require the
explicit `--synthetic` switch and are not research findings.

Read [methodology](docs/METHODOLOGY.md) before interpreting return windows, CAR, overlapping events,
benchmark exclusions, fixed chronological splits, model leakage and uncertainty.
