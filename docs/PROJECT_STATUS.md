# Project status — foundation milestone, 2026-11-04

## Implemented and tested
- Installable Python package and CLI; isolated .venv; frozen dependency versions; Ruff and pytest.
- Seven shared domain interfaces plus asset/provider provenance records, with UTC and validation rules.
- CSV import, column mapping, original-post filtering, duplicates/conflicts, source snapshots and quality.
- yfinance daily/hourly adapter, frequency-preserving failures, adjusted bars and quality metadata.
- Local Ollama transport tested using mocked HTTP; prompt/schema validation, retry and cache behavior.
- Calendar primitives: weekends, holidays, early closes, DST, pre-market, after-hours and 24/7 crypto.
- Simple/benchmark returns, feature availability validation and chronological overlap purge.
- Reproducible offline smoke workflow; all mock sentiments/prices/derived records labelled synthetic.
- Core documentation, candidate universe, source assessment, CI configuration and annotation template.

## Actual verification
- Python 3.13.2 on macOS arm64; editable installation and CLI executed successfully.
- 30 offline tests passed. Ruff lint and formatting checks passed. pip check: no broken requirements.
- Smoke: 6 input rows → 2 clean posts; 2 mock sentiments; 3 synthetic bars; 2 events/returns/features;
  1 training and 1 test row. Rerun reproducibility also tested.
- Live Yahoo check, 2024-07-01 through exclusive 2024-07-10: TSLA 6 daily bars, BTC-USD 9 daily bars;
  zero rejected bars. Real outputs: results/live-market-check/run_summary.json; raw snapshots in
  data/raw/market. This verifies a small daily sample only, not historical hourly availability.
- Public GitHub post archive header/sample inspected; no full real post corpus accepted or imported.

## Implemented but not empirically verified
- Live local-model inference: adapter exists, but no installed model was selected/run for this project.
- Financial relevance/sentiment accuracy, sarcasm handling and confidence calibration.
- Live hourly downloads and all configured candidates across the full target period.
- CI workflow file exists; no hosted CI run or remote publication has occurred.

## Planned, not implemented
- Source-specific corpus conversion, full archive audit and expected-session market gap audit.
- Production multi-asset event alignment, overlap clustering, first/repeated asset/topic classification.
- Market-model expected returns, CAR, descriptive/event-study inference, uncertainty and robustness.
- Predictive baselines, linear/regularized/tree models, full cross-validation, performance plots.
- Manual annotation scoring/adjudication tooling and publication-quality figures/report.

## External constraints and known limitations
- No audited original-post archive covers the desired recent 3–5 years. Candidate GitHub data ends
  in 2022, lacks explicit repost status and sampled numeric IDs show possible precision loss.
- No evidence yet establishes matching full-period hourly Yahoo coverage. No silent daily fallback.
- Calendar/pandas/NumPy emit deprecation warnings under the installed versions; tests pass. Warnings
  remain visible; upgrades need revalidation. No current observed functional failure.
- Quality reports describe accepted range and rejected rows, not proof of dataset completeness.
- Synthetic events only demonstrate interfaces; they must never enter empirical results.
- Model knowledge cutoff, mature engagement and adjusted historical prices need point-in-time review.

## Recommended next milestone
Audit and select a recent original-post corpus; produce asset-by-frequency coverage tables, then
agree any necessary historical-period/hourly trade-off. Select a local foundation model and label
an evaluation sample. Build production event alignment only after those evidence checks.
No project-manager action is required to use the completed foundation. Scope changes or paid data
would require an explicit later decision.
