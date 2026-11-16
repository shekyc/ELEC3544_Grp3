# Source evaluation — inspected 2026-11-04

The intended 3–5-year history relative to this project is approximately November 2021–November 2026.
No currently audited archive establishes complete original-post coverage over that window.

| Candidate | Evidence inspected | Suitability / remaining issues |
|---|---|---|
| [DudekCode GitHub archive](https://github.com/DudekCode/Elon-Musk-All-Tweets) | Repository description and first 4 KiB of the public CSV | Described as 2010–2022, scraped April 2023; too old for full target window. Actual sample has UTC-labelled timestamps, text, user, IDs, reply references, engagement. No explicit repost-status field. Some numeric Id values disagree with IDs in Tweet.URL, suggesting earlier precision loss; audit full file before adoption. Not approved as empirical corpus. |
| [Andrada Olteanu Kaggle archive](https://www.kaggle.com/datasets/andradaolteanu/all-elon-musks-tweets) | Public indexed dataset description/columns; page exposed no readable body | Candidate includes IDs, text, timestamps, user, retweet/reply metadata and engagement. File download, current coverage, license and completeness not verified; do not infer currency from “present” in description. |
| [Kulgen Kaggle archive](https://www.kaggle.com/kulgen/elon-musks-tweets/activity) | Public indexed dataset description | Advertised 2012–2017 coverage: unsuitable for desired research window. |

The GitHub sample is a header/field audit only: no full archive download or empirical cleaning has
been claimed. Reply references could support a dataset-specific reply classifier, but absence of a
repost flag is not evidence of originality. RetweetCount is engagement, not a boolean repost status.
Preserve Id as text and compare against status URL IDs; do not silently repair without an audit trail.
The generic CSV adapter is ready for sources once their metadata semantics are documented.
No Kaggle credentials were requested or used. No raw post corpus is redistributed with this project.

## Market source
Use [yfinance history/download documentation](https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html).
Explicit intervals, adjusted OHLCV, UTC boundaries, request metadata, raw response hash and failure
reports are implemented. The documentation warns of limited intraday history; actual provider
retention can differ by interval and change over time. Attempt requested data and report failures;
never infer full historical hourly coverage from a successful recent request. Coverage reports
currently give observed range and invalid rows; a complete expected-session/gap audit remains next.

## NLP transport
[Ollama chat API](https://docs.ollama.com/api/chat) supports schema-constrained JSON and non-streaming
responses. This is transport capability, not proof of financial sentiment accuracy. Model metadata,
training cutoff and manual annotation must be evaluated before research inference.

## Acquisition gate for next milestone
Audit several recent candidate archives at file level, including monthly counts, ID preservation,
author, original/reply/repost semantics, missing timestamps and licenses. Establish intersection with
market coverage for each asset/frequency. Present any necessary change to the scientific period or
hourly scope to the project manager before adopting it. Archive titles are not completeness evidence.

## Verified integration status (2026-11-16)
The uploaded original dadalyndell `all_musk_posts.csv` is now imported directly with string IDs and
unknown original-status exclusion. The full archive yields 14,018 originals and the approved study
window 1,234; 24 nonempty months do not prove completeness. Older branch conversions filled missing
flags with false and used unsafe numeric inference in sampling; do not reproduce those conversions.

The user successfully tested historical Alpaca SIP with Basic credentials. New collection uses the
stock bars endpoint with explicit SIP/split adjustment and 30-minute source bars, then regular-session
aggregation. Unit tests mock requests; full live coverage is not yet verified. Crypto USD coverage is
still unresolved: Binance's successfully tested public archive is USDT, not USD. An explicit local
USD candle importer is available without silently changing the research currency.


## Kraken USD acquisition resolved (2026-11-16)
Official source: https://support.kraken.com/articles/360047124832-downloadable-historical-ohlcvt-open-high-low-close-volume-trades-data
Public archive parts at `https://assets.kraken.com/marketing/institutions/Kraken_OHLCVT_Full.zip.part00`
through part04. Standard browser User-Agent requests succeeded with HTTP 206 after earlier default
Python-agent requests returned 403. No credentials, account, CAPTCHA bypass or paid access used.
Native members XBTUSD, ETHUSD and XDGUSD at 60 and 1440 minutes were extracted with ranged ZIP reads;
XBT maps to BTC, XDG maps to DOGE, quote remains actual USD. ~7.7 MB downloaded rather than 9.5 GB.
Each member's ZIP CRC verified; member/range SHA256 and server ETags recorded. Full archive SHA256
was not verified. Every expected study day is available, but hourly gaps remain: BTC 7, ETH 8,
DOGE 2,417 (2,411 in 2020). No-trade omissions are documented by Kraken and daily OHLCV agrees with
aggregated available hourly trades. See the local crypto coverage and cross-frequency audit JSONs.
This supersedes the earlier unresolved USD-source status; representativeness and event attrition
remain analysis limitations, not unresolved API access.
