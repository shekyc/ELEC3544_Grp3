# ELEC3544 — Musk sentiment and market reactions

Working Python foundation for **Analysing the Market Impact of Elon Musk's Social Media
Sentiment on Stocks and Cryptocurrencies** (Group 3, Fall 2026).
The proposal was inspected on 2026-11-04. This milestone builds ingestion, validated interfaces,
a local foundation-model adapter and reproducible verification. It does **not** contain final
research findings, trained predictive models or a validated production event-study pipeline.

## Setup

From this repository root (Python 3.13 recommended; declared minimum 3.11):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-lock.txt
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/musk-sentiment --help
```

The lock is the exact tested foundation environment; package wheels may differ by platform.
For fresh dependency resolution use `pip install -e '.[dev]'` inside an environment with
network access. Later research dependencies are available as `.[research]` but not yet used.
No account keys or paid services are needed. `.env.example` documents this; no .env loader is used.

## Offline reproducible example

```bash
.venv/bin/musk-sentiment smoke
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Inspect `results/smoke/summary.json`. Every fixture price, sentiment and event is **synthetic**.
The example imports six rows, keeps two original posts, caches mock sentiment, validates three
market bars, and writes two event/return/feature records with a purged chronological split.
It exercises interfaces; its fixed prices and neutral sentiment have no empirical interpretation.
The smoke fixture uses the first configured asset as a wiring example only.

## Import historical posts

```bash
.venv/bin/musk-sentiment import-posts path/to/posts.csv \
  --source 'dataset URL and version' --source-timezone UTC \
  --column-map configs/post_columns.example.json
```

The mapping is canonical field name → source column name. Canonical CSVs need no mapping.
Required fields: post_id, text, created_at, author. IDs remain strings; never load them as floats.
Supply explicit is_reply and is_repost booleans (true/false or 1/0). Unknown status is excluded,
with counts in the quality report. Metadata may require a dataset-specific conversion first;
the generic importer never guesses that missing flags mean original content. Naive timestamps
require an explicitly justified source timezone; DST ambiguity is rejected. Quote posts are not
classified separately yet and require a corpus-specific policy before empirical inclusion.

Raw snapshots go to `data/raw/posts/`; cleaned data and quality reports to
`data/processed/posts/`. Reruns replace derived outputs but never overwrite raw snapshots.
Use separate output directories for distinct datasets/runs. Source text is preserved; only
whitespace is normalized for NLP. No broad punctuation/emoji stripping is performed.

## Collect market data

```bash
.venv/bin/musk-sentiment collect-market --tickers TSLA BTC-USD \
  --start 2024-07-01 --end 2024-07-10 --interval 1d
```

Omit tickers/dates to use `configs/project.toml`. End dates are exclusive. The candidate universe
includes stocks, ETFs and multiple cryptocurrencies and is editable. Final selection remains
coverage- and relevance-driven. Hourly data requires `--interval 1h`; unavailable requests fail
with reports and a nonzero exit status, never silently falling back to daily data.
Inspect each quality report and run_summary.json before using an output. A failed run may leave
an older successful derived file; status and provenance must match the intended run.


## Reproducing the cleaned Elon Musk posts (Kaggle dadalyndell 2025)

The large raw and processed data files are intentionally not stored in Git.

To recreate the cleaned posts used in this project:

1. Download `all_musk_posts.csv` from the Kaggle dataset “Elon Musk Tweets 2010 to 2025” by dadalyndell.
2. Place it in `data/raw/posts/`.
3. Create a cleaned version with an explicit author column:

```bash
python -c '
import pandas as pd
df = pd.read_csv("data/raw/posts/all_musk_posts.csv", low_memory=False)
df["author"] = "elonmusk"
df["likeCount"] = pd.to_numeric(df["likeCount"], errors="coerce").fillna(0).astype(int)
df.to_csv("data/raw/posts/all_musk_posts_clean.csv", index=False)
'
```

4. Import using the project mapping:

```bash
musk-sentiment import-posts data/raw/posts/all_musk_posts_clean.csv \
  --source kaggle-dadalyndell-2025 \
  --column-map configs/kaggle_musk_columns.json \
  --author elonmusk \
  --output data/processed/posts
```

The resulting clean posts and quality report will appear in `data/processed/posts/`.

Market data for TSLA, BTC-USD and DOGE-USD can be collected with:

```bash
musk-sentiment collect-market --tickers TSLA BTC-USD DOGE-USD \
  --start 2023-01-01 --end 2025-01-01 --interval 1d
```

## Local foundation-model inference

Install and run Ollama separately with a suitable **local** model already downloaded, then:

```bash
.venv/bin/musk-sentiment nlp data/processed/posts/posts.json --model YOUR_LOCAL_MODEL
```

The adapter requires locally installed weights and records their digest. It uses loopback only,
validated JSON output, bounded retries and a content-addressed cache. No model download is
triggered. Real inference and financial sentiment accuracy have not yet been validated.
Successful records persist if some requests fail; errors are recorded for incremental retry.
The interchangeable Provider protocol also supports future approved providers.

## Documentation

- [Architecture](docs/ARCHITECTURE.md): interfaces, modules and planned stages.
- [Data dictionary](docs/DATA_DICTIONARY.md): fields, timing and missing-value conventions.
- [Methodology](docs/METHODOLOGY.md): alignment policy and leakage controls.
- [Source evaluation](docs/DATA_SOURCES.md): candidate archive evidence and coverage risks.
- [Decisions](docs/DECISIONS.md): defaults and unresolved scientific choices.
- [Project status](docs/PROJECT_STATUS.md): verified capabilities and next milestone.

Raw data, generated results and local caches are ignored by Git. CI runs offline checks on
Python 3.13; CI itself is not verified until the project is pushed to a configured remote.
