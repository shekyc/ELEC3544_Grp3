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

## 3. Collect verified Kraken USD crypto history

```bash
.venv/bin/musk-sentiment collect-kraken
```

No account, key or payment is needed. The collector reads selected byte ranges from Kraken's public
split ZIP, verifies member CRCs, snapshots the downloaded ranges/CSV members and records hashes and
ETags. It downloads native hourly and daily BTC/USD, ETH/USD and DOGE/USD files (about 7.7 MB total),
not the complete 9.5 GB archive. The full archive SHA256 is therefore not claimed verified.

Live verification: all three have 731 daily bars in 2020–2021. Hourly counts are BTC 17,537,
ETH 17,536 and DOGE 15,127 out of 17,544 possible hours. Kraken omits no-trade intervals; these gaps
are never filled. Native daily bars remain usable on days with no-trade hours. Every compared daily
OHLCV agrees with the aggregation of available hourly records. The collector also obtains the
available 2019 estimation buffer and January 2022 outcomes; DOGE/USD begins December 2019.

See `crypto_study_coverage.json`, `crypto_cross_frequency_audit.json` and `kraken_manifest.json` under
`data/processed/market`. Sparse DOGE hourly coverage affects event eligibility, particularly in 2020.
No USD/USDT conversion or mixed-venue patching is performed.

The generic `import-crypto` command remains available for other audited USD CSVs with columns
`ticker,quote_currency,timestamp,open,high,low,close,volume`; timestamps must be UTC ISO or UNIX seconds.
`aggregate-crypto-daily` is a stricter optional local aggregation requiring 24 hourly observations;
it is separate from the native Kraken daily download.

## 4. Extract sentiment and evaluate against the annotation reference

The original 1,234-post Sol Light/v5 run is retained as the conservative price-expectation baseline
in `data/processed/nlp` and `data/processed/nlp_sol_full`. Following the user's approved definition
revision, v6 extracts favourable/unfavourable financial stance and business/adoption information
without requiring a price forecast. Sol Light/Low, corpus, asset universe and schema are unchanged.
V6 is also preserved at `data/processed/nlp_sol_v6_full` and `data/processed/nlp_sol_v6`.
Current v7 adds targeted rules: include substantively involved neutral assets, distinguish market
effect horizons from event dates, and avoid assumed benefits from product-price changes or jokes.
It uses separate `data/processed/nlp_sol_v7_full` batches and `data/processed/nlp_sol_v7` outputs.
The Codex subagent workflow does not use the Ollama command or a paid API.
Frozen inputs contain only post ID/text/time and the configured asset universe, plus prompt/schema.
No Astra labels or future market outcomes are supplied to extractors. Human review was not completed.

After every batch exists, validate and import the saved model outputs:

```bash
.venv/bin/musk-sentiment import-nlp-batches data/processed/nlp_sol_v7_full --output data/processed/nlp_sol_v7
```

This is an offline import, not a new model call. It rejects incomplete coverage, changed inputs,
model/prompt provenance mismatches and invalid outputs; it creates pipeline-compatible
`data/processed/nlp_sol_v7/sentiments.json`, per-post cache entries, summary and empty error list only after
all batches validate. Changed model outputs require a new output directory. Rerunning extraction
requires new model execution with separately frozen inputs; do not relabel old outputs as a new run.
The requested model/effort are recorded; an immutable backend weights digest is unavailable for
the hosted subagent. Outputs are real-post model extractions, not human ground truth.

`annotations/study_sample.csv` is the locked 160-post sample balanced over eight quarters.
At the user's request, GPT-6 Astra annotated it as `sheky(astra)` in
`annotations/study_labels_sheky_astra.csv`: 162 rows, 160 posts, 48 dev and 112 test posts.
The `.provenance.json` sidecar records model-generated origin; this is **not human ground truth**.
All IDs, text, dates, split/stratum, score signs and multi-asset rows were validated independently.
The sample itself is unchanged. See [annotation rules](docs/ANNOTATION.md).

```bash
.venv/bin/musk-sentiment nlp data/processed/study/posts.json --model YOUR_INSTALLED_MODEL --output data/processed/nlp_local_v7 --cache data/processed/nlp_local_v7_cache
.venv/bin/musk-sentiment score-nlp annotations/study_labels_sheky_astra.csv data/processed/nlp_sol_v7/sentiments.json --split dev --reference-type model --output results/nlp_v7_dev_agreement.json
```

The `nlp --model` command above remains an optional local Ollama route only.

These scores measure agreement with Astra, not independently established human accuracy. Freeze
model/prompt using dev only before examining test scores. Both models can share errors and historical
training leakage; annotations remain provisional research references rather than observed truth.
Because test-labelled examples were inspected while diagnosing v5's definition, the old 112-post
NLP test is no longer an untouched test for v6/v7. Any repeat comparison is descriptive only. No market
returns were consulted to revise the definition. Retain the baseline Excel and JSON unchanged.

No model is downloaded automatically. Model digest, prompt version and parameters are recorded;
cache keys invalidate when these or input text change. To compare already-installed models, use
separate `--output` directories and score them on dev; freeze the choice before inspecting test.
The v7 prompt supports every configured asset and avoids mapping SpaceX-only news to TSLA.
A valid JSON response is not evidence of financial sentiment accuracy.

## 5. Run analysis and inspect coverage before interpreting results

```bash
.venv/bin/musk-sentiment research --nlp data/processed/nlp_sol_v7/sentiments.json --output results/study_v7
.venv/bin/musk-sentiment plot-study results/study_v7
```

Outputs include validated events, rejected events with reasons, input hashes, coverage, subgroup
summaries, bootstrap intervals, exploratory sign-flip tests/FDR, isolated-event sensitivity,
chronological model scores and predictions. Missing inputs remain visible; partial diagnostic
outputs must not be presented as completion of the full study. All-synthetic runs require the
explicit `--synthetic` switch and are not research findings.

Read [methodology](docs/METHODOLOGY.md) before interpreting return windows, CAR, overlapping events,
benchmark exclusions, fixed chronological splits, model leakage and uncertainty.

Current empirical run: `results/study_v7`. Required TSLA/AAPL and SPY/QQQ prices passed coverage
checks; BTC/DOGE USD prices are present. The user approved skipping remaining unmentioned assets.
`review_summary.json` and `event_validation.json` summarize 1,358 validated event/horizon rows;
`models.json` includes explicit skips for small samples. Only TSLA qualifies for prediction tests.
See `docs/PROJECT_STATUS.md` for findings, incomplete scientific objectives and interpretation limits.

## 6. Separate one-minute extension

Checkpoint before extension: `a0f6bdf`. UTC/source/DST verification is saved under
`results/minute_preflight`; the original hourly/daily results stay in `results/study_v7`.
With existing Alpaca credentials exported locally (never printed), collection can be reproduced:

```bash
.venv/bin/musk-sentiment collect-minute --provider alpaca
.venv/bin/musk-sentiment collect-minute --provider kraken
.venv/bin/musk-sentiment research-minute
.venv/bin/musk-sentiment plot-minute results/study_minute_v7
```

Minute analysis refuses to overwrite an existing completed run: use `--output results/NEW_RUN`
for a new run. Frozen settings are in `configs/minute.toml`; outputs include 5/15/30-minute price,
volume, trade-count and volatility summaries, session assignments, explicit exclusions, day-cluster
and common-horizon sensitivity, prediction scores/skips, and matched-post old/new comparisons.
Regular, extended, next-opening and 24-hour crypto observations are never pooled into one cohort.
The plot uses day-cluster uncertainty; significance tests and sample counts are in the JSON tables.

## 7. Validate the minute findings without changing them

```bash
.venv/bin/musk-sentiment validate-minute
.venv/bin/musk-sentiment plot-validation results/validation_minute_v7
```

Rules are in `configs/validation.toml`; results are separate from both earlier runs. Outputs include
balanced pre/post profiles, historical matched non-post controls, explicit unmatched cases, medians,
leave-one-day-out results, isolated-post tests and individual price charts. Existing completed
validation runs cannot be overwritten; use `--output` for a separate run. Read the sample counts
and dependence warnings before presenting a matched-control result as statistically established.
