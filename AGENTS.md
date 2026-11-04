# ELEC3544 project instructions

## Scope and working relationship
Implement the proposal's full stock/ETF/crypto research scope. The initial assignment is the
technical foundation, not the entire six-week study. Do not turn fixtures into findings.
The project manager delegates routine implementation decisions. Ask only for scientific scope
changes, substantial methodological trade-offs, paid access, credentials or destructive operations.
Do not call paid APIs or download large model weights without approval.

## Architecture and conventions
Python 3.11+; verified environment recorded in requirements-lock.txt. Source lives in
src/musk_sentiment; reusable logic must not live only in notebooks. Use Pydantic contracts in
schemas.py, TOML configuration, UTC-aware times, explicit units, and JSON artifact boundaries.
Keep raw snapshots immutable and content-addressed. Preserve IDs as strings. Record provenance,
model/prompt versions and synthetic status. No credentials, raw datasets or generated results in Git.
Use concise docstrings and clear errors. Keep optional analysis dependencies separate.

## Scientific integrity
Unknown original-post status is excluded, never assumed false. Never silently replace hourly
with daily prices. Current adjusted histories and mature engagement counts are not point-in-time
features. Confidence is uncalibrated. First mention means first observed in the documented corpus.
No future information in NLP prompts. Model training cutoff can itself introduce historical leakage.
Use chronological purged evaluation; no causal claims from proximity or correlation.
Do not mark a research stage operational until its empirical prerequisites are validated.

## Verification and maintenance
Run .venv/bin/ruff check ., .venv/bin/ruff format --check ., .venv/bin/pytest -q and
.venv/bin/musk-sentiment smoke after meaningful changes. Tests must be offline and deterministic;
live provider checks are explicit, separate commands. Add behavioral tests for boundary conditions.
Update docs/PROJECT_STATUS.md with implemented/tested, untested, planned and external blockers.
Maintain README, architecture, dictionary, methodology and decision log. Keep commits logical.
No subagents are required by this file.
