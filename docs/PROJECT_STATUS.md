# Project status — sheky/merge, 2026-11-16

## Implemented and tested
- Branch created from main; remote tansy/cyrus reviewed and selectively reused. No wholesale merge
  of their datasets, labels or generated predictions. See INTEGRATION.md for source revisions.
- Approved post window 2020–2021; configurable stocks, sector/market ETFs and crypto retained.
- Conservative original Kaggle CSV import: exact string IDs, status-URL author/ID validation,
  unknown-status exclusion, immutable source snapshots, full monthly study quality and source comparison.
- Alpaca SIP adapter: explicit feed/adjustment, paginated read-only requests, retries, regular-session
  30-minute-to-hour/day aggregation, expected calendar coverage and missing/duplicate-bar handling.
- Explicit USD crypto import plus verified public Kraken archive collector using bounded byte ranges,
  ZIP CRC/ETag checks, raw snapshots, native hourly/daily candles and cross-frequency/coverage audits.
- Full-universe v5 NLP prompt, local installed-model adapter, cache/model/prompt provenance and input
  fingerprints. Empirical study rejects predictions from a different corpus/universe or legacy runs.
- Exact-ID quarterly annotation sampling, locked dev/test split and multi-asset scoring.
- Multi-asset events: explanatory and predictive endpoints separated, first/repeated asset/topic
  mentions, benchmark CAR, pre-event market-model CAR, gaps and rejected events reported.
- Subgroup analysis, overlap clustering, bootstrap intervals, exploratory sign-flip tests/BH-FDR,
  isolated-event sensitivity, alternate hourly/daily horizons.
- Zero/mean/lagged baselines; linear/Ridge/tree models with market-only vs NLP features, chronological
  validation/test with overlap purging, training-only preprocessing, paired improvement intervals.
- Offline orchestration and plots, synthetic-data separation, hashes and diagnostic manifests.

## Actual verification and local outputs
- **52 offline tests passed**; Ruff lint/format passed; original smoke passed (2 synthetic events).
  Extended synthetic integration covers research outputs and figure rendering, not empirical findings.
- Research dependencies installed and frozen in requirements-lock.txt; pip check passed.
- User confirmed successful historical SIP curl sample on Alpaca Basic. This is user-reported sample
  access, not a live test of the new collector or proof of every asset/year's coverage.
- Original uploaded CSV: 55,099 rows. New full archive import: 14,018 originals; 828 unknown-status,
  40,124 reply/repost and 129 other-author exclusions. Immutable raw snapshot retained locally.
- **1,234 study posts** in 2020–2021; all 24 months represented. This is observed coverage, not proof
  of archive completeness. Files: data/processed/study/posts.json and quality.json.
- New **160-post** blinded annotation sample across eight quarters: annotations/study_sample.csv,
  with manifest/hash. User-authorized Astra reference labels now cover all 160 posts in 162 rows,
  annotator sheky(astra), separate CSV/provenance. These are model-generated, not human ground truth.
- User-requested GPT-6.1 Sol Light/Low development run independently labelled all 48 dev posts
  without Astra labels or test posts. Exact IDs and SentimentOutput contracts validated; 20 relevant
  posts and 16 asset labels. Local JSON/provenance: annotations/study_dev_sol_light*.json. Excel
  review: outputs/sol-dev-review/Sol_Light_Development_Review.xlsx, with blank interpretation/comment
  fields and nonblank/nonzero attribute highlights. Human review is pending. This is a development
  extraction artifact, not an NLPRecord production run or a frozen model selection.
- Live Kraken download verified: 7,702,404 bytes for six CSV members plus directory/ranges. All three
  assets have 731 daily study bars. Hourly BTC 17,537/17,544; ETH 17,536/17,544; DOGE 15,127/17,544.
  Missing hours are preserved. All native daily OHLCV match available-hour aggregates across 1,127
  BTC days, 1,127 ETH days and 775 DOGE days including buffer data. No prices were fabricated.
- Source reconciliation: all Tansy pilot/extract IDs found in uploaded CSV; all 150 Cyrus sample
  texts represented after whitespace/entity normalization, but only 10 exact IDs match. Diagnostic
  candidates are not automatic identity repairs. Evidence: data/processed/study/branch_source_audit.json.

## Implemented but not empirically verified
- Full Alpaca asset-by-period coverage, aggregation correctness against live examples, rate limits.
- Cross-venue representativeness of Kraken and consequences of sparse DOGE 2020 hourly trading.
- v5 model inference/accuracy on revised corpus, sarcasm/rare assets, model choice/cutoff effects.
- Real event counts, estimation residuals, statistical assumptions, model scores and plots.
- Hosted CI has not run; local tests pass. Pandas/NumPy/calendar deprecation warnings remain visible.

## Remaining work and external blockers
1. Set Alpaca credentials locally (not available to this process); collect hourly/daily stock/ETF data
   and inspect coverage, including prelisting gaps and buffers for estimation/outcomes.
2. Crypto data access is resolved with Kraken USD. Audit event attrition from no-trade gaps and
   insufficient early-DOGE estimation history. No paid provider or model download was initiated.
3. Compare installed local models against the user-authorized Astra dev reference, freeze model/prompt,
   then test. Report model-reference agreement; independent human ground truth is not established.
4. Run complete NLP, inspect all failures and then execute real research. Partial diagnostic outputs
   cannot establish completion of the full multi-asset study.
5. Review benchmark choices, confounding events, serial dependence, market-model diagnostics and
   sample sizes. Rolling purged cross-validation/expanded robustness beyond the fixed chronological
   validation/test implementation remains further work if making stability claims.
6. Produce final scientific interpretation, report and presentation from validated outputs.

No empirical market-return findings exist on this branch. Neither synthetic tests nor a valid model
JSON response establish research-stage readiness. The original proposal objectives are retained.
