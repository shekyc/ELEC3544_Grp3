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
