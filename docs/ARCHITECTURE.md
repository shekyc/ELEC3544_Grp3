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

## Integration branch additions (2026-11-16)
- `data/corpus.py`: exact-ID readers, conservative Kaggle import, study-window quality and source comparison.
- `data/alpaca.py`: credentialed read-only SIP collection, immutable response pages, expected session grids,
  complete regular-session aggregation and gaps. `data/local_market.py`: explicit USD crypto import.
- `evaluation/annotations.py`: quarter-stratified frozen samples and exact-ID multi-asset scoring.
- `analysis/study.py`: validated event windows, mentions, market model/CAR, clustering and inference.
- `models/research.py`: chronological overlap-purged baselines and market-only/NLP comparisons.
- `analysis/run.py`: offline orchestration, separate synthetic/empirical inputs, hashes, rejection/coverage
  artifacts and figure export. CLI exposes each stage; research dependencies are optional until used.
- Uploaded root CSV, processed data, annotations and results remain local and Git-ignored. Source branches
  remain intact; `docs/INTEGRATION.md` records what was reused and why other artifacts were excluded.

- `data/kraken.py`: bounded seekable HTTP range reader over public archive parts, member CRC and ETag
  validation, native USD hourly/daily contracts, study coverage and cross-frequency consistency audit.
  `collect-kraken` is an explicit live command; its tests use local fake ranged responses.
- Annotation scoring records `reference_type` and `reference_annotators`; model reference agreement
  is distinct from independent human accuracy. Astra annotations/provenance remain local and ignored.
- `nlp/batches.py`: offline import of actual Codex subagent extraction outputs. Frozen manifests and
  batch input/output sidecars bind corpus, configuration, prompt, schema, model and reasoning effort.
  Validate all batches before publishing any final NLPRecord dataset; preserve input fingerprints,
  per-post cache entries and immutable evidence snapshots. This importer does not perform inference.
- Prompt v6 changes the measured sentiment construct without changing JSON contracts. Baseline v5
  outputs and Excel remain in place; revised batches and final records use `nlp_sol_v6_full` and
  `nlp_sol_v6`. Keep prompt versions distinct in cache/research runs. Import requires the currently
  loaded prompt to match frozen inputs; old v5 records remain usable directly as baseline data.
- V7 uses `nlp_sol_v7_full` and `nlp_sol_v7`, preserving both previous runs. Schemas and downstream
  return-window logic are unchanged; the revised prompt affects extraction only.
