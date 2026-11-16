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
  Under user-approved v6, sentiment is the favourable/unfavourable/balanced stance or business,
  valuation, adoption or prospects information conveyed by the text. Explicit price forecasts are
  not required. Endorsements and beneficial/adverse developments can carry direction; bare names,
  dates and routine recruiting can be neutral. Scores measure textual sentiment, not future returns.
  Mixed signals should be explained. Missing context uses neutral only as an explicitly unresolved,
  low-confidence fallback, not a confident absence of direction. Do not target a class balance.
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

## User-authorized Astra reference (2026-11-16)
The user selected GPT-6 Astra instead of a human annotator for this run. The resulting file is
`annotations/study_labels_sheky_astra.csv`, annotator_id `sheky(astra)`, with a provenance sidecar.
It covers all 160 posts in 162 rows: 61 relevant posts, 99 irrelevant, two multi-asset posts. Source
text, IDs, dates and split/stratum are unchanged. No future prices or other model predictions were
shown to the annotator. Model-generated does not mean fabricated fixture: synthetic=false refers
to real source posts; annotation_kind=model_generated and is_human_ground_truth=false are explicit.

Use `score-nlp --reference-type model`. Report reference agreement, not human accuracy. The same
annotator saw dev/test source texts; these annotations do not establish a held-out evaluation of
Astra itself. Human review is optional under the user's current instruction, not an execution blocker.
Model inference errors, subjective scores, missing context and historical knowledge remain limitations.

## v6 revision and baseline preservation
The user approved a text-based financial-sentiment definition after reviewing v5's restrictive
price-forecast interpretation. Preserve v5 outputs at their original paths. V6 is a complete new
Sol Light/Low run with separate inputs, outputs, provenance and Excel review. Neither baseline
predictions nor reference labels are provided to the extractors. The old NLP test examples informed
the definition diagnosis, so they cannot establish untouched test accuracy for this revision.

## v7 targeted rules
- Identify substantively involved assets before sentiment. Uncertain direction does not justify
  omitting a relevant company. A company accepting a token can have neutral sentiment while the
  token has bullish adoption sentiment; include both. Incidental handles and homonyms are excluded.
- A product price change alone is nondirectional unless text supports a benefit or harm. Do not
  invent demand/margin consequences. Brand jokes need an identifiable endorsement or criticism.
- impact_horizon describes a text-supported financial/market effect, not launch or delivery dates.
  Use unknown when only an event schedule is supplied. It does not select study return horizons.
- V5 and v6 remain unchanged; all 2020–2021 posts are independently reprocessed as v7 with Sol Low.
