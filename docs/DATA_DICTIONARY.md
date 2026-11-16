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
