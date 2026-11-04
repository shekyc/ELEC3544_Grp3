# Methodology and scientific safeguards

## Research scope
Keep all three proposal objectives: abnormal returns and financial sentiment; reactions across
stocks/ETFs/cryptocurrencies; variation over periods and first versus subsequent observed mentions.
Foundation-model text interpretation supplies inputs; statistical and traditional ML methods assess
associations and predictive usefulness. No empirical or causal conclusions are available yet.

## Corpus and NLP
Retain original text, emojis and punctuation. Restrict initial empirical corpus to verified original
posts from the named author; uncertain metadata is excluded and reported. Do not infer completeness
from a date range or an archive title. Inspect monthly counts, missing periods and source consistency.
First mention means first observed in the analyzed corpus, not first-ever mention by Musk; future
implementation must define asset/topic grouping and ties and account for left censoring.

Financial sentiment concerns expected asset direction, not general positive language. Multiple
asset sentiments are allowed. The prompt requests ambiguity handling and an unknown horizon when
unsupported; no claim is made that the model reliably follows these instructions in practice.
Confidence is not calibrated. Manual stratified labels (asset, time, relevance, sarcasm, rare cases)
and inter-annotator adjudication are prerequisites to accuracy claims and model selection.
The local model's training cutoff may encode knowledge of historical events; document it and assess
this limitation even when prompts omit future information. Do not add future market-wrap headlines.

## Event alignment: tested primitives and proposed production policy
The next-trading-time helper uses regular US sessions including holidays, early closes and DST;
crypto is continuous. Intraday prices have explicit opening and closing availability times. Never
use a bar's close at its opening timestamp. Reject incomplete and invalid bars.

The synthetic example uses the last completed close before an after-hours/weekend post and the
next full session close. This includes intervening overnight movement and is not an executable
post-publication strategy. It is a contract demonstration, not a full event construction algorithm.
Production work must separately define explanatory event windows and tradable prediction targets.
For daily post-day analysis, the previous observable close may be stale or include substantial
pre/post gaps; report lag and contamination rather than claiming a precise immediate reaction.
For intraday posts, distinguish the in-progress bar from the next complete trading bar. Never silently
replace a requested hour with a daily observation. Missing required endpoints invalidate an event.
Calendar helpers do not model venue-specific halts; missing bars need explicit coverage checks.

Yahoo adjusted OHLC histories are downloaded as a consistent price basis and raw responses are
snapshotted. They can reflect corporate actions unavailable at the historical prediction time;
future forecasting features need point-in-time review, particularly absolute price and volume.
Historical likes/retweets are mature snapshots, not known-at-post predictors. Exclude them unless
observation time proves availability. Current schemas track availability but cannot prove provenance.

## Returns and validation
Simple return = after / before - 1. Benchmark-adjusted return = asset return - benchmark return,
using identical observation endpoints. Benchmarks in the candidate config are provisional: do not
compute self-relative abnormal returns (BTC relative to BTC, or SPY relative to SPY). Decide an
alternative or report raw returns for those benchmark assets. Crypto/equity sessions cannot be
naively joined by date. Market-model fitting requires a pre-event estimation window; CAR aggregates
period abnormal returns, not arbitrary overlapping event returns. Both remain planned.

A basic chronological holdout purges any training label ending at or after the cutoff. Production
cross-validation must purge overlapping windows at every fold, fit scalers/selectors on training
only, and keep concurrent/clustered events together. Avoid tuning on the final test period.
Event clustering, confounders, repeated testing, serial dependence and clustered/bootstrap uncertainty
must be addressed before reporting significance. These are planned safeguards, not completed tests.

## Planned model and reporting stages
Historical-mean and zero-signal baselines; lagged-return baseline; linear/regularized regression;
tree model; market-only vs NLP-augmented comparison; MAE, RMSE, directional accuracy and out-of-sample
improvement. Study temporal/repeated-mention variation and alternative windows/assets/periods.
Report null findings and limitations honestly. Model fitting, statistical intervals/significance,
robustness suites and publication figures are outside this foundation milestone.
