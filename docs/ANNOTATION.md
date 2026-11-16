# Annotation rules for the 2020–2021 corpus

Adapted from the useful distinctions in Tansy's guidelines and Cyrus's random/keyword development
and test sampling design. The old three-ticker restriction and 2023+ labels are not carried forward.

- Use `annotations/study_sample.csv`; keep IDs as text (Excel can round them). Never rebuild it
  with pandas' automatic JSON number inference. The sampler refuses to overwrite a locked sample.
- Read only the supplied post and historical context available then; never inspect future prices.
- `market_relevant`: `true`/`false`. Financial relevance is different from emotional positivity.
- Assets come from `configs/project.toml`, including stocks, sector/market ETFs and crypto.
  Do not infer TSLA exposure from SpaceX/Starlink news alone. A clearly supported link is needed.
- One row per post/asset; duplicate the row for multiple assets, keeping split/stratum and ID.
  Irrelevant or broad-topic-only posts have a blank ticker. No duplicate post/ticker labels.
- `sentiment`: bullish, bearish, neutral. Scores: bullish (0,1], bearish [-1,0), neutral exactly 0.
  A named product or company alone is not automatically bullish.
- `topic`: products, production, adoption, valuation, regulation, technology, financing, macro,
  or other. `impact_horizon`: intraday, short_term, long_term, unknown; do not invent a horizon.
- `ambiguous`: true/false; explain sarcasm, missing context and mixed signals in notes.
- Enter annotator_id. Have a second person independently check a stratified subset and adjudicate
  disagreements into a separate final label file; keep the originals. Agreement assessment remains
  a human review step, not something the pipeline fabricates.
- Develop prompts/model choice on dev only, then freeze and score test once. Enrichment means
  the sample's relevance proportion is not an unbiased estimate of corpus prevalence.

`score-nlp` reports relevance precision/recall, exact asset-set agreement and sentiment accuracy
against all gold asset labels (missing predicted assets count as errors). It refuses incomplete
relevance/annotator fields, invalid scores, conflicting labels, and missing exact-ID predictions.
Old out-of-period labels remain on their source branches, not mixed into this evaluation.
