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
- Full-universe versioned NLP prompt, local installed-model adapter, cache/model/prompt provenance and input
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
- **77 offline tests passed**; Ruff lint/format passed; original smoke passed (2 synthetic events).
  Extended synthetic integration covers research outputs and figure rendering, not empirical findings.
- Research dependencies installed and frozen in requirements-lock.txt; pip check passed.
- Live Alpaca SIP collection now verified with the locally supplied credentials. TSLA/AAPL and
  required SPY/QQQ benchmarks have complete regular-session hourly/daily coverage and buffers.
  NVDA/RIVN were already collected before the user requested skipping remaining unmentioned assets.
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
- User subsequently accepted the development run and authorized full extraction with the same model
  and prompt. **All 1,234 posts processed** in 13 frozen GPT-6.1 Sol Light/Low batches; no missing or
  duplicate IDs. Full corpus/config/prompt/schema and sidecar hashes checked before NLPRecord import.
  Outputs: data/processed/nlp/sentiments.json, summary.json, errors.json (empty), and per-post cache.
  Raw batch inputs/outputs/provenance and snapshots retained in data/processed/nlp_sol_full.
  Model-labelled counts: 379 relevant posts, 196 posts with assets, 199 asset labels (TSLA 167,
  DOGE 22, BTC 7, AAPL 3); 194 neutral, 1 bullish and 4 bearish. These are NLP outputs, not market
  findings. Sparse directional sentiment is a material limitation for downstream comparisons.
  Readable full results: outputs/sol-full-results/Sol_Light_Full_Results.xlsx (1,237 post/asset rows,
  1,234 exact string IDs, nonzero attribute highlights and blank interpretation/comment columns).
- Post-freeze Astra reference agreement: test relevance 81.25%, exact asset sets 85.71%, asset
  sentiment 38.24% (13/34 reference assets). These measure cross-model agreement, not human accuracy.
  Results under results/nlp_sol_{dev,test}_agreement.json. No prompt revision followed test scoring.
  This statement describes the v5 run; the subsequently authorized v6 revision is described below.
- **V6 revised full extraction completed:** user approved financial stance/business/adoption meaning
  without requiring price forecasts. All 1,234 posts reprocessed with Sol Light/Low in 13 frozen
  batches; exact coverage, schema, model/prompt/config hashes and provenance validated. Separate
  outputs: data/processed/nlp_sol_v6/{sentiments,summary,errors,baseline_comparison}.json; errors empty.
  Counts: 266 relevant posts, 197 posts/asset labels (TSLA 165, DOGE 22, BTC 7, AAPL 3), comprising
  117 bullish, 10 bearish, 70 neutral. Matched baseline assignments changed neutral to bullish 115
  times and neutral to bearish 6 times; two asset assignments added, four removed. These are changes
  in the measured sentiment construct, not evidence of improved accuracy or price predictability.
  All 1,320 baseline files verified unchanged, including previous Excel, raw batches and caches.
  No market outcomes or previous model labels were supplied to the v6 extractors. The old NLP test
  examples informed the preceding definition diagnosis, so it is no longer untouched for v6.
  Review workbook: outputs/sol-v6-review/Sol_Light_V6_Financial_Sentiment_Review.xlsx.
- **V7 targeted rerun completed:** all 1,234 posts independently reprocessed with Sol Light/Low.
  Complete exact-ID/schema/provenance validation passed; no missing/duplicate IDs and errors empty.
  Current outputs: data/processed/nlp_sol_v7; frozen batches: data/processed/nlp_sol_v7_full.
  Counts: 242 relevant posts, 190 asset-assigned posts, 194 asset labels (TSLA 161, DOGE 23, BTC 7,
  AAPL 3), comprising 96 bullish, 9 bearish, 89 neutral. All assigned-post impact horizons are unknown;
  configured return windows remain independent. Targeted checks confirm both assets in the three
  Tesla/crypto payment examples, neutral bare product-price changes/brand joke, and no inferred
  market-effect duration from product schedules. These checks do not establish independent accuracy.
  All 2,642 v5/v6 artifacts verified unchanged. Review workbook:
  outputs/sol-v7-review/Sol_Light_V7_Financial_Sentiment_Review.xlsx.
- Live Kraken download verified: 7,702,404 bytes for six CSV members plus directory/ranges. All three
  assets have 731 daily study bars. Hourly BTC 17,537/17,544; ETH 17,536/17,544; DOGE 15,127/17,544.
  Missing hours are preserved. All native daily OHLCV match available-hour aggregates across 1,127
  BTC days, 1,127 ETH days and 775 DOGE days including buffer data. No prices were fabricated.
- Source reconciliation: all Tansy pilot/extract IDs found in uploaded CSV; all 150 Cyrus sample
  texts represented after whitespace/entity normalization, but only 10 exact IDs match. Diagnostic
  candidates are not automatic identity repairs. Evidence: data/processed/study/branch_source_audit.json.

## Empirical V7 run completed
- User authorized proceeding with the four mentioned assets and their required benchmarks; no
  further NIO/XLY/XLK collection. Their six missing configured files remain visible in the manifest
  and do not remove any V7 event. The configured NLP universe and 2020–2021 post scope are unchanged.
- TSLA/AAPL/SPY/QQQ each have 3,526/3,526 hourly and 505/505 daily study bars; including buffers,
  5,421 hourly and 777 daily bars. No duplicates, invalid OHLCV, missing session bars or hourly/daily
  aggregate mismatches. Daily series reuse the same immutable SIP 30-minute snapshots. NVDA is
  also complete; RIVN begins November 2021 and has no gaps within its available span.
- Coverage evidence: data/processed/market/equities_{collection_manifest,coverage_audit}.json.
- results/study_v7: 190 unique posts, 194 post–asset pairs, 1,358 event/horizon rows, zero rejections.
  Counts at every horizon: TSLA 161, DOGE 23, BTC 7, AAPL 3. Existing crypto gaps do not intersect
  required event windows. TSLA/AAPL use all 120 estimation pairs; DOGE hourly uses 105–120.
  All 1,358 timestamp/return arithmetic checks passed in event_validation.json. No synthetic rows.
- Descriptive groups, isolated-event sensitivity, chronological model evaluation and 21 standard
  figures generated. v7_daily_uncertainty.png adds cluster means and uncertainty; review_summary.json
  consolidates event counts and preliminary diagnostics. Market outcomes did not change the NLP.
- Only TSLA meets model sample thresholds: final test uses 128 training and 33 evaluation events
  at each horizon. DOGE has only two final-test events, BTC zero and AAPL two; these model groups
  are explicitly skipped. NLP improvement is mixed, not evidence of reliable predictive advantage.
- One-day event-weighted raw means: TSLA +1.37%, DOGE +14.60%, BTC +0.37%, AAPL +3.47%.
  These daily windows include pre-publication movement. DOGE's market-model CAR mean is +4.83%,
  but its equal-cluster CI includes zero; isolated-event evidence is sparse (3 DOGE daily events).
  BTC abnormal returns are null because its configured benchmark is itself, not fake zero CAR.
- Only four first-observed asset mentions exist (three with abnormal returns). Inference is
  suppressed below five clusters; a reliable first-mention boost cannot be established here.

## Implemented but not empirically verified
- Uncollected NIO/XLY/XLK histories, unnecessary for the current V7 mentioned-asset analysis.
- Cross-venue representativeness of Kraken and consequences of sparse DOGE 2020 hourly trading.
- Independent semantic accuracy of v7 extraction, sarcasm/rare assets, model choice/cutoff effects.
- Estimation residual assumptions, confounding controls and robustness beyond the current fixed
  settings. Real counts/scores/plots exist, but do not establish causal or prospective validity.
- Hosted CI has not run; local tests pass. Pandas/NumPy/calendar deprecation warnings remain visible.

## Minute extension: completed after checkpoint a0f6bdf
- User requested commit first, then timezone verification. All 1,234 original CSV/cleaned UTC
  timestamps match; ID-derived timestamps agree within the source's second precision. DST checks
  around both years' transitions and an early close passed before implementation continued.
- Separate native one-minute collection: 3,173,623 bars including buffers for TSLA/AAPL/SPY/QQQ
  and BTC/DOGE USD. Four stock/ETF RTH series have 196,354 / 196,354 / 196,349 / 196,354 of
  196,410 expected study minutes. No filling. Every complete reconstructed hour exactly matches
  the older hourly OHLCV; the incomplete hours are explicitly recorded in minute_preflight.
- Source/model labels and previous market/results files preserved. Validation evidence:
  results/study_minute_v7/validation.json; 3,753 baseline files and all 21 old study input hashes
  are unchanged. Minute source hashes, timezone audit and deterministic replay are recorded.
- Separate 5/15/30-minute windows: 453 accepted event/horizon observations, 129 rejected.
  TSLA regular: 32/32/30; extended: 10/7/3; next-opening: 83/83/83. BTC: 7/7/7;
  DOGE: 21/21/21; AAPL regular: 2/2/2. These are repeated horizon observations, not 453 posts.
  Missing pre-publication bars account for 46 rejections, missing window/benchmark minutes for 64,
  and session boundaries for 19. Extended-hour sparsity is a major limitation, not repaired.
- DOGE differs from the earlier own-price availability check: one post lacks a baseline, and the
  July 1, 2021 post fails the aligned BTC benchmark check. Activity reference history is also
  insufficient for 34 otherwise valid observations; price outcomes remain available for those.
- Relative volume, trade count and realized volatility use past same-time medians (20 candidate
  windows, minimum 10 complete). Post-event activity is never used as a prediction input.
- **Stronger short-window DOGE association:** 15-minute day-cluster mean return +5.10% (21 posts,
  19 days); volume 8.61×, trades 7.83×, volatility 4.00× reference (13 eligible activity posts).
  DOGE 5/15-minute return sign tests and activity tests survive BH-FDR and same-day sensitivity;
  the 30-minute return sign test does not. Effects remain observational and venue/sample-specific.
- Matched DOGE post comparison (ordinary event means, different entry definitions): new 15-minute
  forward return +4.48%, old next-hour forward return -0.015%, old next-day forward return -1.17%.
  The earlier coarse prediction windows can miss the immediate response; this is not proof of an
  executable trading edge or improved forecast accuracy.
- No signed/absolute sentiment correlation survives multiplicity correction. TSLA price reactions
  remain weak; activity averages rise modestly but the corrected median tests are not convincing.
  BTC and AAPL are small samples. Larger absolute activity does not establish NLP predictive value.
- Final prediction tests qualify only for TSLA next-opening: 69 training / 14 evaluation events.
  Regular-hours TSLA has only four final-test events; other groups fail the fixed minimums.
  NLP adds no dependable advantage: the 30-minute Ridge improvement still underperforms simple
  no-change/historical-mean forecasts; activity-prediction improvement intervals are not positive.
- 71 offline tests, lint, formatting and smoke passed. Boundary tests cover DST, holidays, early
  closes, next-minute alignment, missing bars, past-only references/features, purge boundaries,
  daily clustering, collector pagination/resume and credential exclusion. All 453 observed returns,
  volume/trade totals and realized volatilities were independently recalculated successfully.
- New outputs: results/study_minute_v7, including descriptive/model tables, exclusions, day-cluster
  and common-horizon sensitivity, old_comparison.json, and minute_outcomes.png. Earlier results
  remain in results/study_v7; NLP remains V7 and the date scope remains 2020–2021.

## Three follow-up validation checks completed
- Separate output: results/validation_minute_v7. Frozen V7 labels, 2020–2021 scope and all 43
  earlier coarse/minute result artifacts remain unchanged. No new market API calls were needed.
- Balanced event profiles: 126 eligible post/asset paths, 68 exclusions. Counts: DOGE 12 posts
  on 11 days, BTC 4, TSLA regular 22, extended 3, next-opening 83 and AAPL 2. Next-opening profiles
  show only 0..60 minutes after opening; closed-market pre-publication paths are not invented.
  Group figures and 126 individual price charts are saved with an index.
- DOGE profile subset rose an average 2.59% during the preceding 30 minutes, then 7.61% over the
  publication-minute-based first five minutes. A visible post-publication jump coexists with prior
  movement; the pre-return median sign test is not significant. These profile outcomes differ in
  sample and alignment from the primary next-full-minute returns and must not be mixed silently.
- Matched controls: 232 of 453 event/horizon cases qualify; 221 do not. Matching uses only prior
  conditions and non-post times, with strict completeness/caliper requirements. At 15 minutes only
  four DOGE posts qualify, connected into one component by reused control dates: formal inference
  is suppressed. TSLA's eligible matched contrasts do not survive multiplicity correction.
  Thus the matched-placebo check is inconclusive for DOGE, not an additional confirmed effect.
- DOGE 15-minute result is not driven by a single day: removing each entire day leaves the day-mean
  return between +4.27% and +5.70%; event median is +2.98%. The largest influence is 2021-04-28.
- Twelve isolated DOGE posts retain a +6.19% mean 15-minute return (bootstrap 95% interval
  +3.14% to +9.64%; corrected sign-test q=0.028). Nine with sufficient activity references retain
  volume 6.66×, trade count 7.19× and volatility 4.03×; corrected q=0.028 for each.
- Verdict: the DOGE association survives important outlier/isolation checks, but causality and
  predictive usefulness remain unproven. Pre-existing moves, scarce comparable non-post controls,
  incomplete original-post coverage and modern-model historical knowledge remain limitations.
- 77 offline tests pass, including precondition timing, non-post boundaries, matching constant
  features, session-safe profiles, whole-day omission, strict isolation and historical controls.

## Remaining work and limitations
1. Interpret the completed event study and prediction outputs, including overlap sensitivity,
   benchmark dependence, small samples, historical LLM leakage and mixed NLP improvement.
2. First-mention comparisons/indicators are computed. An explicit sentiment-by-first-mention
   interaction is still not implemented; four first mentions cannot support a convincing boost claim.
3. Independent human ground truth remains unestablished, following the user-approved model-reference
   workflow. Do not relabel model agreement as accuracy or tune NLP using these inspected returns.
4. Unmentioned-asset spillover analysis, alternative benchmark/estimation settings and rolling purged
   evaluation are not implemented/run. Do not represent the present results as completing every
   original scientific objective. The user approved skipping further unmentioned-asset downloads.
5. Prepare final interpretation and presentation. Preserve adverse/unsuccessful results.

## Eight-step progress after empirical V7 run
| Step | Status |
|---|---|
| 1. Stock/ETF prices | Required assets and benchmarks collected and audited; complete study coverage. |
| 2. NLP model setup | Sol Light/Low operational. |
| 3. Annotation reference | Astra 160-post model reference exists; no independent human ground truth. |
| 4. USD crypto history | Collected; gaps preserved; no V7 event-window rejections. |
| 5. Validate/freeze NLP | V7 frozen; targeted qualitative/structural checks passed. |
| 6. Full corpus extraction | Complete: 1,234 V7 outputs; earlier runs preserved. |
| 7. Research analysis | Coarse and minute studies completed, including 5/15/30-minute returns/activity, separate sessions, sensitivity and eligible prediction tests; limitations above. |
| 8. Interpretation/slides | Results available; final presentation pending. |

Readiness evidence: results/step7_readiness_v7.json. Run evidence: results/study_v7/manifest.json,
review_summary.json and event_validation.json. Proceed to interpretation/slides with the explicit
limitations above. The original development run retains validation from 2021-01-01 and its final split from
2021-07-01. A separately authorized frozen 2022 holdout is now complete, as recorded below.
These results are retrospective associations, not causal findings.


## Frozen 2022 holdout completed (2026-11-17)
- Prior state committed as `6d7a2e3`; 1,426 frozen input/result files remain hash-identical.
- Availability validated with actual 2022 Alpaca SIP responses and Kraken archive records.
  TSLA/AAPL/SPY/QQQ each contain all 97,710 expected regular-session minutes. Crypto gaps
  remain explicit; no gap filling or proxy quote currencies.
- 876 original posts, all 12 months, UTC/post-ID timing checked. Identical V7 Sol Light:
  TSLA 62, AAPL 7, DOGE 4 asset labels. No prompt/universe/settings revisions.
- 169 accepted event windows, 50 rejected under the original rules. Models trained only
  on purged pre-2022 events; historical mention counts continued. Both TSLA regular and
  next-opening cohorts qualify for prediction; other cohorts remain below minimum samples.
- No NLP improvement interval is wholly positive across price/activity prediction. No
  day-cluster summary or sentiment association survives correction. AAPL overlap-level
  correlations narrowly pass but represent six posts on two days, not robust replication.
- DOGE has only two usable 15-minute posts; insufficient to confirm or refute the earlier
  association. Retain the adverse observed returns without declaring a general reversal.
- All three frozen validations rerun: 53 balanced profiles, 90 matched event windows,
  79 unmatched, influence/isolation checks. Audited 169 outcomes and 450 control uses.
- Verification: 81 deterministic offline tests; lint, format and synthetic smoke pass.
- Evidence: `results/study_minute_v7_2022/REPORT.md`, `comparison.json`, `models.json`,
  `verification.json`; `results/validation_minute_v7_2022/` and `oos_2022_preflight/`.
- Remaining: presentation; independent human label validation and historical LLM leakage
  remain unresolved. No further model selection on 2022 can call it untouched testing.
