# Methodology — 2020–2021 implementation

## Population and provenance
Original posts dated [2020-01-01, 2022-01-01) UTC; verified string ID and author from the source
status URL. Unknown reply/repost metadata is excluded, not converted to false. Preserve raw bytes,
source identifiers, import rejection categories, and every month's counts. Nonempty months do not
establish completeness. Full post text is not a command or instruction to the model.

Asset universe remains configurable across stocks, market/sector ETFs and crypto. Current candidates
are not a final coverage-approved universe. RIVN's prelisting period cannot be filled. Current SPY
and BTC benchmark mappings point to themselves: these assets receive raw returns only; no fake zero
abnormal returns. Other mappings are provisional scientific choices to review before final analysis.
Crypto uses USD quote prices; USDT cannot be relabelled USD. No silent hourly/daily substitution.

## Financial NLP and human validation
v5 incorporates the useful financial/linguistic distinction and ambiguity handling from Tansy's work
without its fixed three-ticker list. Private-company ecosystem news alone does not establish TSLA
exposure. Multi-asset directions and broad relevant topics with no defensible ticker are allowed.
Topics use stable general categories, not future event-specific examples. Confidence is uncalibrated.
No future prices or headlines enter prompts. The modern model's training may nevertheless contain
2020–2021 outcomes: this remains retrospective research, not a point-in-time NLP backtest.

Quarter-balanced random and keyword-enriched sampling adapts Cyrus's dev/test approach while keeping
IDs as strings. Freeze dev/test membership; use dev for prompt/model selection, test after freezing.
Obtain independent labels/adjudication and inspect sarcasm/rare-asset errors. Test metrics include
relevance, asset-set agreement and gold-asset sentiment accuracy; relevance accuracy is not sentiment
accuracy. Enriched sampling does not estimate population prevalence. No empirical NLP accuracy has
yet been measured on this new corpus.

## Prices and availability
Alpaca: explicit SIP, split adjustment, pagination; source 30-minute bars are aggregated from the
regular session open. Thus 09:00–09:30 premarket does not enter the first 09:30–10:30 hourly bar.
Early closes and DST use exchange calendars. A final 1h-labelled session bar can be 30 minutes.
Every required constituent must exist; duplicate constituents invalidate that aggregate. Daily bars
are aggregated from the same regular-session inputs for a consistent session definition.
Crypto is continuous UTC; a daily aggregate requires all 24 hours. No gap filling is performed.
The collector requests 2019 estimation history and January 2022 outcomes without adding posts outside
the approved two-year window. Provider gaps and prelisting gaps remain visible in quality reports.

Current split-adjusted history is not point-in-time history. Models use returns/volatility, not
absolute adjusted prices, mature engagement counts or current fundamentals. Keep this limitation
in reporting. No claim is made about real-time execution latency or achievable trading returns.

## Two distinct outcomes
For explanation, take the latest completed close before/at the post, then the first bar closing
strictly after the post and the configured number of successive trading bars. For a mid-bar post,
this includes price movement before publication within the unfinished bar; for an after-hours post,
it includes overnight/weekend movement. Record baseline/post/outcome times and interpret accordingly.

For prediction, enter at the **next complete bar's open at/after publication**, then exit at the
configured horizon's close. This target is stored separately from the explanatory return. Features
use only completed bars at publication; no in-progress close is treated as already observable.
Missing required asset or benchmark bars reject the event rather than advancing to a later price.
Default horizons: hourly 1/3/6/24 trading bars, daily 1/3/5 sessions. These are configurable defaults,
not selected after inspecting returns. A horizon of 24 equity bars is not 24 wall-clock hours.

## Mentions, abnormal returns and uncertainty
Asset mentions and asset/topic mentions are counted chronologically across the entire prepared
corpus, before market-coverage rejection. Tied timestamps use string post ID as a deterministic tie
break. First means first observed since corpus start, never first-ever; topic counts use model
categories and are affected by classification errors and left censoring.

Raw return = ending close / baseline close - 1. Benchmark return uses identical endpoints.
Benchmark CAR = sum of successive asset-minus-benchmark simple returns, not the difference of two
compounded returns. Market-model CAR = sum(asset return - alpha - beta × benchmark return).
OLS fits up to 120 prior matched return pairs, all ending before/at publication; at least 60 pairs
and nonzero benchmark variance are required. Otherwise market-model CAR is null, never replaced by
another definition. Estimation-window and residual diagnostics require empirical review.

Describe asset, asset class, year, sentiment, first/subsequent asset and asset/topic groups.
Overlapping explanatory/predictive windows form time clusters. Report ordinary event means and
separately equal-cluster means. Bootstrap 95% intervals resample cluster means; suppress inference
below five clusters. Exploratory two-sided sign-flip tests assume independent clusters and symmetric
cluster means under the null. BH-FDR adjusts p values across the emitted table; confidence intervals
remain unadjusted. Neither procedure removes confounding or all serial dependence. Do not describe
these as causal effects. Isolated-event sensitivity excludes clusters with multiple events; alternate
horizons, benchmarks and estimation settings can be rerun into separate result directories.

## Prediction evaluation
Separate models per asset/frequency/horizon. Validation begins 2021-01-01; final test begins
2021-07-01. Training labels must finish strictly before the boundary; overlapping clusters crossing
into evaluation cannot enter training. Validation labels ending in final test are excluded.
Vectorizers/scalers fit only on training. Fixed hyperparameters avoid tuning on final test:
linear regression; Ridge alpha=1; random forest 100 trees, depth 3, minimum leaf 5, fixed seed.
Compare market-only return/volatility inputs against NLP-augmented sentiment, first-mention and topics.
Zero, historical mean and lagged-return × horizon baselines are included. Report MAE, RMSE,
directional accuracy and paired NLP MAE improvement with cluster bootstrap intervals. A minimum of
20 training and 5 evaluation events is needed to fit; skipped groups are explicitly listed.
This is a fixed chronological validation/test implementation, not a completed rolling CV study.

## Empirical acceptance and remaining work
Outputs are diagnostic until full corpus/market coverage and human-label quality are checked.
No synthetic rows enter empirical runs. Input hashes, model versions, omissions and limitations are
written beside results. Before submission: inspect estimation residuals, major confounding events,
model coverage/sample sizes, benchmark suitability and sensitivity results; assess whether first
mentions are too sparse for any inference. Extend to rolling purged folds if stability claims require
it. Final narrative/slides and scientific interpretation are not generated from synthetic tests.


## Update: model annotation and verified USD data (2026-11-16)
The user explicitly replaced the human annotation step with GPT-6 Astra, annotator `sheky(astra)`.
Treat this as a model-generated reference set, not human gold. Dev/test membership is unchanged;
small-model evaluation reports agreement with that reference and carries shared-error/training-leakage
limitations. Independent human review is not a required execution gate for the authorized workflow.

Kraken native USD hourly and daily candles are now collected directly from its public archive.
Kraken omits intervals without trades. Do not interpolate those hours or interpret a missing hour
as an observed zero return. The event constructor rejects required missing endpoints. Native daily
bars cover all 731 study days even where no trades occurred in some hours. Daily prices/volume were
cross-checked against available hourly trades, not filled hourly prices. Native daily records may
therefore be used independently of the stricter 24-observation local aggregation helper. DOGE/USD
starts 2019-12-19, so early-2020 market-model daily estimation can remain insufficient and return null.
