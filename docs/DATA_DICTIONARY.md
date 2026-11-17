# Data dictionary (schema version 1)

All shared contracts are in src/musk_sentiment/schemas.py. Unknown fields are rejected.
Timezone-aware datetimes normalize to UTC; naive datetimes are rejected. JSON null means unknown,
never zero. Numeric scores/prices/returns must be finite. IDs are strings to preserve precision.

| Contract | Key fields and conventions |
|---|---|
| RawPost | post_id, text (original), created_at, author, source; nullable is_reply/is_repost; likes ≥0 or null; engagement_observed_at nullable; synthetic |
| CleanPost | RawPost with original-status flags both false and normalized_text (whitespace only); sorted by time then ID |
| Asset | ticker, asset_class (stock/etf/crypto), calendar, benchmark, aliases; universe is configurable |
| MarketObservation | ticker, bar_start/bar_end UTC, interval 1d/1h; open/high/low/close in quote currency per unit; volume in provider units; adjusted, source, synthetic |
| AssetSentiment | ticker, bullish/bearish/neutral; score in [-1,1] with matching sign, neutral 0; confidence [0,1] uncalibrated |
| SentimentOutput | post_id, market_relevant, assets (multiple allowed), topics, impact_horizon, ambiguity text |
| NLPRecord | output plus provider, model/digest, prompt_version, cache_key, parameters, synthetic |
| PostAssetEvent | event_id, post_id, ticker, posted_at, prediction_at ≥ posted_at; mention_index ≥1 and first_observed_mention; sentiment_score; synthetic |
| EventReturn | event_id/ticker, baseline_at ≤ prediction_at < outcome_at, interval, horizon_bars; raw_return, optional paired benchmark_return/abnormal_return; synthetic |
| FeatureRow | event_id/ticker, prediction_at, features_available_at ≤ prediction_at, label_end > prediction_at; finite named features, target; synthetic |

Returns are decimal fractions (0.01 = 1%). Current EventReturn supports simple benchmark subtraction,
not market-model residuals or CAR; those extensions need an explicit versioned contract.
Daily equity boundaries are regular session open/close, including early closes. Daily crypto bars
are midnight UTC through the next midnight. Intraday close time is capped at session close.
A 1h-labelled final equity bar can last only 30 minutes; interval is provider frequency, not duration.
Market volume units and adjusted values are provider conventions; do not compare raw volume
across asset classes without normalization. Synthetic source records must remain labelled synthetic.

CSV mappings map canonical names to actual headers. Boolean inputs are true/false or 1/0 only.
Engagement snapshot times are never inferred from post time. Reports contain input/accepted/excluded
counts, invalid-row reasons, source hash, observed time range and monthly accepted counts.
Market reports include request dates/frequency, retrieval time, row count, rejected rows and raw path.
Observed coverage does not imply complete coverage. Preserve the report alongside every dataset.

## StudyRow and integration outputs
`StudyRow` extends analysis without changing the legacy `EventReturn` contract. It includes
post_id/ticker/asset_class/interval/horizon, posted_at, baseline_at, outcome_at (explanatory), entry_at
and label_end (predictive), mention_index, topic_mention_indices, topics, sentiment_score, raw_return,
benchmark_return, benchmark_car, market_model_car, estimation_n, alpha/beta, predictive_return,
features and synthetic. CARs are sums of simple-return residuals, all returns in decimal units.
A null market_model_car means insufficient estimation coverage/variance or no independent benchmark.

Alpaca source strings identify SIP, split adjustment and regular-session 30-minute aggregation.
Quality reports contain requested dates, raw snapshot paths, expected counts, missing starts and
rejected input records. Crypto CSV imports require literal quote_currency=USD and an exact configured
ticker; timestamps are timezone-aware ISO or integer UNIX seconds, never inferred milliseconds.
Annotation sample CSV preserves post_id as text and adds split/stratum. Labels are initially blank.
Study outputs carry coverage, rejected events, input SHA256 hashes and a diagnostic status; model
scores and bootstrap tables must be interpreted with the adjacent manifest and methodology.

Agent-extracted `NLPRecord.input_sha256` hashes the canonical per-post prompt payload. Parameters
also record reasoning effort, annotator identity and batch input/output/provenance hashes. The
model name is the requested hosted model, not a verified immutable weights digest. Batch manifests
bind the exact source corpus/configuration and prompt/schema; synthetic=false denotes real source
posts, not human authorship. `summary.json` counts post relevance separately from per-asset labels.

V6 retains the same schema but changes the documented sentiment construct: favourable/unfavourable
financial stance or business/adoption/prospects information, not a required explicit price forecast.
Do not combine v5 and v6 scores as interchangeable measurements. The ambiguity field records the
textual basis, mixed signals or an explicitly unresolved neutral fallback; confidence refers to the
whole interpretation, not merely ticker recognition. It remains uncalibrated.

V7 keeps the v6 sentiment meaning. The assets list includes substantively involved targets even if
neutral; omission is not a substitute for uncertain direction. impact_horizon refers to a supported
financial/market effect (intraday, days, weeks-or-longer), not the scheduled date of a business event.

## One-minute extension
- `MinuteBar`: `t` UTC minute start; `o/h/l/c` prices; `v` base-unit volume; `n` trade count;
  optional `vw` provider VWAP. Implicit bar end is `t + 60 seconds`. Provenance/adjustment and
  SHA256 are in each ticker's manifest; JSON files are partitioned by UTC date.
- `MinuteEvent`: string post/event IDs, asset, `regular/extended/next_opening/crypto_24h` cohort,
  explicit 5/15/30-minute horizon, UTC publication/baseline/entry/end, and entry delay in seconds.
- `forward_return`: entry-open to end-close fractional return. `baseline_to_end_return` is separate;
  `opening_gap_return` applies only to next-opening cases. `benchmark_adjusted_return` is matched
  compounded-return difference, not the old market-model CAR. BTC's benchmark fields are null.
- `volume`, `trade_count`, `realized_volatility`: window totals and unannualized sqrt(sum log-return²).
  `reference_*` are past matching-window medians; `reference_windows` records complete comparisons.
  `relative_*` are dimensionless ratios; null means insufficient history or zero reference.
- `features`: only pre-publication five-minute market measurements and their age.
  `features_end_at <= posted_at` is enforced; missing input bars disable prediction eligibility.
- `descriptive.json` clusters overlapping windows. `day_cluster_sensitivity.json` clusters dates;
  `common_horizon_sensitivity.json` holds post membership constant across 5/15/30-minute windows.
  Summary sign tests concern medians; bootstrap intervals concern equal-cluster means.
- `old_comparison.json`: same post IDs, different horizon/entry definition; not an accuracy test.

## Minute validation artifacts
- `event_profiles.json`: one balanced path per eligible post/asset, publication-minute anchor,
  offsets -30..60 (0..60 for delayed opening), price path, pre/post returns and activity-rate bins.
  Explicit rejections; group means use equal day weights and pointwise bootstrap intervals.
- `matched_placebos.json`: accepted and rejected matches, historical control timestamps, observed
  precondition vectors, RMS distances, actual feature endpoint, raw control outcomes and effect
  contrasts. `return_difference` is in fractional-return units; activity effects are ratios.
  `independent_components` joins actual dates that share control dates; it is not the post count.
- `influence.json`: event/day medians, leave-one-day-out means, influential date, isolated-event
  count/mean/CI/p/q. `loo_min`/`loo_max` are sensitivity bounds, not confidence limits.
- `figures.json`: group figures and individual post profile paths; missing profiles remain listed
  as rejections rather than interpolated charts.

### 2022 holdout artifacts
- `study_2022/posts.json`: 876 verified originals in [2022-01-01, 2023-01-01), UTC.
- `nlp_sol_v7_2022`: frozen V7 Sol Light extraction; separate from development labels.
- `market_minute_2022`: new minute histories through the January 2023 outcome buffer.
- `market_minute_combined_2022`: manifest references to old pre-2022 and new 2022+ files.
- `study_minute_v7_2022`: test-only events/models and comparison with development results.
- `prior_mentions`: full development label counts, including events rejected for market gaps.
- `comparison.json`: paired earlier/test day-cluster summaries; missing groups are null.
- `verification.json`: preservation hashes, empirical recalculation/control audits and checks.
- `validation_minute_v7_2022`: same three robustness checks, with all observed 2020–2022
  original posts used for non-post-control screening and isolation.
