# Decision log — 2026-11-04

1. Use the empty workspace directly as repository root; no redundant nested repository.
2. Use Python, Pydantic, pandas, yfinance, exchange-calendars, httpx, pytest and Ruff. TOML config,
   argparse CLI and JSON artifacts keep a university project inspectable. Avoid servers/databases.
3. Preserve every proposal asset class. Eight configurable candidates illustrate breadth; neither
   their count nor final membership is fixed. XNYS regular hours are a shared US-equity session proxy;
   use venue-specific handling where instruments require it.
4. Set the requested candidate lookback to 2021-11-04 through exclusive 2026-11-04. This is a desired
   coverage window, not evidence that posts exist for it. Do not silently adopt a much older corpus.
5. Default example collection to daily. Hourly remains explicit and independent; no fallback changes.
   Joint 3–5-year post/hourly coverage is unresolved, requiring evidence before scientific trade-offs.
6. Reject unknown original-post status. This sacrifices uncertain rows rather than relabelling replies.
   Duplicate ID conflicts in core content are excluded; differing engagement counts retain first input
   row and remain unsuitable as historical predictors without snapshot timing.
7. Preserve raw bytes in content-addressed snapshots; use atomic derived writes. Keep downloaded
   datasets local and out of Git. Record source URL/version and hash; do not assume redistribution rights.
8. Implement a loopback-only Ollama provider with installed local model digest, no automatic pulls.
   Real model choice, hardware suitability and annotation quality remain unverified. No commercial API.
9. Synthetic workflow is intentionally separate and labelled; it verifies wiring, not research validity.
10. Implement schemas and small calendar/return/purge primitives now. Production event builder,
    market model, inferential statistics, predictive fits and figures follow in later milestones.
11. Exact installed dependencies recorded in requirements-lock.txt; test CI on Python 3.13.
    Upstream NumPy/pandas/calendar deprecation warnings are documented, not hidden.
