# Architecture

A single installable Python package and CLI, with no database or orchestration framework.
Small JSON arrays are transparent, validated interchange artifacts for this foundation;
move to chunked JSONL/Parquet once corpus size warrants it, preserving schema contracts.

| Layer | Responsibility | Foundation status |
|---|---|---|
| data/posts.py | Snapshot CSV, normalize UTC, deduplicate, filter, report | Implemented |
| data/market.py | yfinance history, adjusted OHLCV, timestamp bounds, reports | Implemented |
| schemas.py | RawPost, CleanPost, MarketObservation, NLPRecord, PostAssetEvent, EventReturn, FeatureRow | Implemented |
| nlp | Provider protocol, local Ollama, versioned prompt, cache, validation, retries | Implemented; real inference unverified |
| alignment/calendar.py | Sessions, early closes, holidays, next trading time | Implemented primitives |
| analysis/returns.py | Simple and benchmark-adjusted returns | Implemented primitives |
| features/validation.py | Chronological holdout with overlapping-label purge | Implemented primitive |
| models, evaluation, visualization | Fits, diagnostics, plots | Reserved packages; not implemented |
| smoke.py | Synthetic integration example across contracts | Implemented |

Flow: source CSV → immutable snapshot → RawPost validation → CleanPost → NLPRecord →
future production event builder → EventReturn → FeatureRow → future modeling/evaluation.
Market collection independently produces MarketObservation records for the event builder.
Each artifact includes schema_version; timestamps are UTC and synthetic status follows outputs.

Cache identity covers input text, timestamp, asset universe, prompt text/version, output schema,
provider/model digest, parameters and synthetic status. Cache hits are revalidated.
Writes of derived JSON use an atomic rename. Raw snapshots use exclusive creation and SHA-256.
Concurrency is not coordinated: use separate output directories for parallel runs.

Tests use fixture providers and fake Yahoo transports. The smoke pipeline is not the production
alignment engine: it uses a fixed after-hours/weekend example and manually neutral benchmark.
Additional provider adapters must implement the same Protocol and preserve provenance.
