# Manual annotation preparation

Use configs/annotation_template.csv as the initial manual-label interchange template. One row per
post/asset/annotator; use a blank ticker for irrelevant or broad-topic-only posts. Do not mix labels
with model outputs. Keep source post IDs unchanged. Avoid displaying future prices to annotators.

Before evaluation, define a stratified sampling plan across time, assets, relevance and ambiguity;
include replies/reposts only to assess filtering, not to silently expand the research population.
Two independent labels and a documented adjudication pass are recommended. Labels should describe
asset-price expectations, not emotional tone. Record disagreement and uncertainty; do not force a
bullish/bearish label. Horizons may be unknown. Freeze a held-out evaluation sample before tuning.

The template is available; sampling, annotation execution, agreement metrics and model scoring are
not implemented in the foundation. A measured evaluation must precede claims about NLP accuracy.
