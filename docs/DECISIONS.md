# Decision log — 2026-11-04

1. Use the empty workspace directly as repository root; no redundant nested repository.
2. Use Python, Pydantic, pandas, yfinance, exchange-calendars, httpx, pytest and Ruff. TOML config,
   argparse CLI and JSON artifacts keep a university project inspectable. Avoid servers/databases.
3. Preserve every proposal asset class. Eight configurable candidates illustrate breadth; neither
   their count nor final membership is fixed. XNYS regular hours are a shared US-equity session proxy;
   use venue-specific handling where instruments require it.
4. Set the requested candidate lookback to 2021-11-04 through exclusive 2026-11-04. This is a desired
   coverage window, not evidence that posts exist for it. Do not silently adopt a much older corpus.
5. Default example collection to daily. Hourly remains explicit and independent; no fallback changes.
   Joint 3–5-year post/hourly coverage is unresolved, requiring evidence before scientific trade-offs.
6. Reject unknown original-post status. This sacrifices uncertain rows rather than relabelling replies.
   Duplicate ID conflicts in core content are excluded; differing engagement counts retain first input
   row and remain unsuitable as historical predictors without snapshot timing.
7. Preserve raw bytes in content-addressed snapshots; use atomic derived writes. Keep downloaded
   datasets local and out of Git. Record source URL/version and hash; do not assume redistribution rights.
8. Implement a loopback-only Ollama provider with installed local model digest, no automatic pulls.
   Real model choice, hardware suitability and annotation quality remain unverified. No commercial API.
9. Synthetic workflow is intentionally separate and labelled; it verifies wiring, not research validity.
10. Implement schemas and small calendar/return/purge primitives now. Production event builder,
    market model, inferential statistics, predictive fits and figures follow in later milestones.
11. Exact installed dependencies recorded in requirements-lock.txt; test CI on Python 3.13.
    Upstream NumPy/pandas/calendar deprecation warnings are documented, not hidden.

## 2026-11-16 — Restore original scope; narrow only post dates
- User approved full calendar years 2020–2021, retaining all asset classes and analysis objectives.
- User confirmed a successful Basic-account Alpaca historical SIP sample. Full-period coverage and
  this implementation's 30-minute aggregation are not yet live-verified; credentials remain local.
- Keep yfinance explicitly selectable, add Alpaca SIP equity/ETF history; do not assume it supplies
  2020 crypto, and do not substitute USDT for USD without a scientific decision.
- Request price buffers outside post scope for pre-event estimation and late-window outcomes.
- Copy only useful mapping/guidance/sampling design from the reviewed branches. Rebuild the corpus
  from the newly uploaded original CSV. Unknown original status is excluded; URL IDs/authors checked.
- Preserve original branches and old human work there. Do not reuse out-of-period labels, damaged IDs,
  the incomplete 679-post extract or old generated predictions as revised-study evidence.
- Hyperparameters, windows and chronological boundaries are configurable, explicit defaults, not
  tuned claims. Empirical validation/coverage, confounding review and final interpretation remain gates.


## 2026-11-16 — Astra annotation and Kraken USD
- User explicitly requested GPT-6 Astra annotation as sheky(astra). Use a separately recorded model
  reference set, not fabricated human labels; evaluation exposes reference type and annotator IDs.
- Resolve crypto with Kraken spot USD for BTC/ETH/DOGE and the BTC benchmark, keeping venue consistent.
  Extract native hourly and daily archive members; preserve no-trade gaps and do not silently fill.
- Native daily candles are independently valid when some intraday hours have no trades; validate
  their OHLCV against available hourly aggregates. Keep hourly event exclusions and early-DOGE
  estimation shortages visible. No alteration of the approved post scope or quote currency.

## 2026-11-16 — Freeze Sol Light for the full corpus
- User accepted the overall 48-post development review and explicitly requested all study posts
  processed with the same setup. Freeze GPT-6.1 Sol, Low/Light reasoning, v5 prompt and schema.
- Re-extract all 1,234 posts, including development posts, in bounded parallel batches. No previous
  model labels, future prices or outcomes are supplied. Batch context differs from per-post local
  Ollama calls; preserve batch membership and input/output hashes rather than claiming equivalence.
- User trust is authorization to proceed, not completed human review or measured accuracy. Keep
  Astra reference scores labelled model agreement; do not tune the frozen prompt on test results.
- Import through strict corpus/config/prompt/schema/provenance and complete exact-ID checks.
  No paid API, local weights download or change to the research scope was authorized or used.

## 2026-11-16 — User-approved v6 financial sentiment definition
- Correct the construct from narrowly interpreted price expectations to asset-specific favourable,
  unfavourable or balanced financial stance/business/adoption information. Explicit price forecasts
  are not required; do not infer realized returns or force directional balance.
- Rerun all posts with GPT-6.1 Sol Low, unchanged corpus/universe/schema and the frozen v6 prompt.
  Preserve every v5 artifact in place; record baseline hashes and store v6 separately.
- Keep missing-context fallbacks and mixed signals explicit in ambiguity, with lower confidence
  when direction is unresolved. Preserve scores/signs and avoid introducing new schema labels.
- No market outcomes informed revision. Old NLP test examples were inspected during diagnosis;
  future agreement on that set is descriptive, not an untouched evaluation.

## 2026-11-16 — User-approved targeted v7 correction
- Preserve v6's financial-sentiment definition. Include substantive neutral asset targets before
  scoring; separate effect duration from event schedules; do not infer beneficial economics from
  bare product-price changes or automatic endorsement from brand wordplay.
- Rerun all 1,234 posts with Sol Light/Low, unchanged source window/universe/schema/batch membership.
  Preserve both previous runs and their review workbooks; hash-check preservation after completion.
- Review eight-stage readiness without silently expanding dates or adopting the proposed post-2021
  holdout plan. Stock/ETF market collection is still required for the full real-data analysis.

## 2026-11-16 — Required market collection and empirical V7 execution
- User authorized live free Alpaca collection using existing local credentials, coverage checks and
  step 7 using V7. Subsequently requested skipping further unmentioned-asset collection.
- Finish TSLA/AAPL and retain required SPY/QQQ benchmarks. NVDA/RIVN were already collected;
  stop NIO/XLY/XLK downloads. Do not shrink the frozen NLP universe or mutate V7 fingerprints.
- Derive daily bars from the same saved SIP 30-minute pages used for hourly bars, avoiding duplicate
  API downloads. Preserve raw snapshots and disclose missing unneeded files in run manifests.
- Run the existing fixed chronological analysis into results/study_v7. No date expansion, prompt
  retuning on market outcomes, changed model thresholds or invented first-mention multiplier.
