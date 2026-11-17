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

## Update: user-approved full Sol extraction (2026-11-16)
Following a 48-development-post Sol Light review artifact, the user accepted the model's overall
judgment and requested full extraction without completing independent human review. Freeze
GPT-6.1 Sol Low reasoning and the unchanged v5 instructions/schema before full inference. Each post
is interpreted from its supplied text, timestamp and permitted assets; no reference labels or market
outcomes are shown. Bounded batches share instructions but request a separate output for every post.
Record batch membership/context and hashes; do not equate batching to independent single-post calls.
All 1,234 posts are reprocessed, rather than silently mixing old development labels into final data.
Assess model-reference agreement only after freezing; do not revise prompts using test agreement.
Modern-model historical knowledge, correlated model errors and uncalibrated confidence remain
limitations. Validation of schema/coverage does not establish semantic accuracy or market findings.

## Update: v6 definition correction and retained baseline
V5's 194/199 neutral asset labels prompted a text-only construct audit. The user authorized v6:
financial sentiment concerns favourable/unfavourable stance or business, valuation, adoption and
prospects information, without requiring an explicit asset-price forecast. Bullish/bearish scores
refer to textual sentiment, not predicted realized returns or market surprise. Generic enthusiasm
does not automatically imply strong financial sentiment. Neutral includes nondirectional or balanced
text; unresolved context must be distinguished in ambiguity and carry lower confidence.

The v5 run remains the conservative price-expectation baseline. V6 reprocesses the whole corpus
with the same Sol Light/Low model, schema and batch partitions, no old labels or market outcomes
shown. Preserve raw inputs/outputs/provenance and verify baseline files unchanged by hashes. The
112-post NLP test was examined during the v5 diagnosis and cannot be called untouched for v6.
Any cross-model or baseline comparison is descriptive. Market prediction holdouts remain governed
by their separate chronological evaluation; no return-based prompt optimization was performed.

## Update: targeted v7 corrections
The user approved separating relevant-asset detection from sentiment assignment, retaining neutral
companies in multi-asset payment/adoption posts. The prompt no longer equates future launch/delivery
dates with a market-impact horizon. Factual product-price changes and brand jokes require supported
direction rather than invented business consequences. Preserve v5/v6 and independently reprocess
the same corpus using v7. No market data or reference labels are supplied during inference. Existing
NLP sample evaluation remains descriptive, not an untouched test. Return windows remain configured
independently of impact_horizon. The suggested 2022+ evaluation split has not been adopted in config.

## Update: first empirical V7 execution
Required stock/benchmark histories were collected and audited before executing the existing fixed
analysis. User-approved omission of further unmentioned-asset downloads does not alter the frozen
NLP universe; missing NIO/XLY/XLK files are reported but reject no current event. Daily securities
bars reuse the exact saved 30-minute pages underlying hourly bars. No prompt/model thresholds or
chronological boundaries were changed in response to results. Only TSLA supports prediction tests;
small other-asset groups and first-mention samples remain limitations. Headline daily explanatory
returns include pre-publication movement and must not be presented as achievable post-entry profit.

## User-approved minute extension (2026-11-16)
Checkpoint commit a0f6bdf precedes this extension. A preflight audit matched all 1,234 cleaned UTC
post timestamps to the original CSV; their ID-derived millisecond times floor to the same seconds.
Alpaca uses UTC minute starts, Kraken uses UNIX seconds, and exchange sessions use America/New_York
with explicit DST/holiday/early-close handling. Hong Kong is only the user's display timezone.

The frozen minute settings are in configs/minute.toml. Native one-minute SIP split-adjusted bars
for TSLA/AAPL and SPY/QQQ, and Kraken spot USD bars for BTC/DOGE, are stored separately. Collection
buffers start 2019-12-01 and end 2022-01-08; post scope stays 2020–2021. Raw snapshots are immutable,
minute files are hash-checked, and no absent price, volume or trade count is filled with zero.

A regular-session post uses the next full minute through 5/15/30 elapsed minutes later. Extended
hours use 04:00–09:30 or regular close–20:00 New York on trading-session dates and are analysed
separately. A window crossing a session boundary is rejected, not spliced into the next session.
Posts outside both sessions form the next-opening group, measured from the next regular opening.
They are delayed responses, not immediate reactions; extended-hours posts are not automatically
reassigned to this group when their data are sparse. Crypto trades continuously in UTC.

Primary forward return is end close / entry open - 1, excluding the partly elapsed publication
minute. Record the sub-minute entry delay (or longer next-opening delay). A separate baseline-to-end
return and next-opening gap retain the prior completed-minute/regular-close comparison; these can
contain pre-publication movement and are not the primary immediate-response outcome.
Benchmark-adjusted minute return is the difference of matched compounded forward returns, not the
older sum-of-bar market-model CAR. BTC has no independent configured benchmark and remains null.

Volume is summed base-asset quantity (split-adjusted shares for SIP; coins for Kraken); trade count
is the number of trades. Realized volatility is sqrt(sum of squared one-minute log returns), using
the entry open for the first return and prior minute closes thereafter; it is not annualized.
Relative activity divides the observed measure by the median of up to 20 earlier same-time windows
(same New York local time/session for equities, same UTC time on prior days for crypto). At least
10 complete reference windows and a positive denominator are required. All references end before
publication. Missing reference history suppresses the relative measure, not the valid price outcome.
Complete-window selection, sparse DOGE trading and Kraken-only volume limit representativeness.

Summaries use equal overlap-cluster means and bootstrap intervals. Sign tests test cluster medians
against zero return or activity ratio one; intervals concern means, so their conclusions can differ.
Sentiment correlations use cluster-level signed and absolute scores. BH-FDR is applied separately
across summary tests and correlation tests; intervals are unadjusted. Same-day clustering and a
common-post set across horizons are separate sensitivity outputs. Clustering does not remove
confounding or dependence across days, and associations do not establish causality.

Prediction retains fixed 2021-01-01 validation / 2021-07-01 test boundaries, 20-train/5-evaluation
minimums, outcome-overlap purging and training-only preprocessing. Targets are forward return and
three relative-activity measures. Inputs are strictly pre-publication five-minute return, realized
volatility, log volume, log trade count and observation age; next-opening cases use the last regular
close available before the post. NLP adds signed/absolute sentiment, topics and first-mention flag.
Post-event activity never enters features. Fixed linear/Ridge/random-forest models are compared with
no-change and historical-mean baselines. Negative activity regression forecasts are not clipped.
This is an exploratory follow-up after inspecting coarse-window results, not a new untouched test.

Old/new comparisons match post IDs and report the older predictive return, not its explanatory
return. Different entry times and horizons mean these comparisons are not tests of improved model
accuracy. Frozen V7 labels and all older result files are preserved and hash-verified.

## Three validation checks: frozen follow-up rules
The user authorized event-time profiles, matched non-post controls, and influential/isolated-event
checks. Settings are frozen in configs/validation.toml before running them. No new period, label
revision or model selection was performed; this remains exploratory validation of inspected results.

Balanced profiles require every minute from 30 minutes before to 60 minutes after publication.
Zero is the start of the publication minute; the reference is the preceding completed close, and
actual publication occurs within the shaded [0,1) minute. Thus the first profile minute includes
some pre-publication seconds, unlike the original next-full-minute prediction target. Whole-window
session crossings and missing minutes reject a profile. Next-opening profiles start at the opening,
with no fabricated pre-publication path. Individual paths and equal-day averages are saved; bootstrap
bands are pointwise and unadjusted. Activity-bin rates divide by the same post's earlier -30 to -5
minute rate, a different reference from the initial 20-day historical activity ratios.

Matched placebos use earlier same-asset, same-session, same-clock-time windows among 60 prior
sessions/days. Crypto also matches weekday/weekend status. Market conditions are measured in the
-30 to -5 minute window; next-opening cases use the prior completed regular-session close before
publication as the reference endpoint. Features are prior return, log volume, log trade count,
log realized volatility and benchmark return where available. Candidate-pool IQR scaling (standard
deviation/constant fallback) defines RMS distance. Select five nearest controls within distance 2,
requiring at least three and an eligible pool of ten. These values were not relaxed after results.
No post-window outcome values enter the distance or selection order; complete source data are required.

A control is excluded if any observed original corpus post occurs between pseudo-publication minus
30 minutes and response entry plus 60 minutes. This covers the longer waiting interval for delayed
openings. Both controls and exclusion windows must lie within the observed 2020–2021 corpus period,
and control outcomes must precede the actual post. The archive is not guaranteed complete, so
"non-post" means no observed corpus post. Actual days that share control dates are joined into
components for inference; fewer than five components suppress intervals/tests. Matching is not a
randomized intervention and does not remove unobserved confounding. Unmatched cases are explicit.

Influence checks retain event/day medians and remove one entire day at a time. The resulting range
is a sensitivity range, not a confidence interval. An isolated event has no other original observed
post from publication minus 30 minutes through response entry plus 60 minutes. Sign tests and
bootstrap summaries use day-level outcomes, with BH-FDR across the isolated-outcome test family.
All earlier minute/coarse artifacts are hash-checked and preserved. Sparse validation subsets must
not be substituted silently for the original sample or described as independent external testing.
