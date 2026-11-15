# Annotation Guidelines – Elon Musk Posts

## Goal
Label each post according to the **expected short-term price impact** on the mentioned asset(s), not the emotional tone of the post.

## Allowed assets
- TSLA
- BTC-USD
- DOGE-USD

No other tickers are permitted. A single post may mention **more than one** of these three assets. Each asset gets its own entry in the `assets` list with its own sentiment and score.

## Core Fields

| Field | How to fill |
|-------|-------------|
| `post_id` | Keep the original ID from the dataset |
| `ticker` | Main asset the post is about (TSLA, BTC-USD, DOGE-USD). Leave blank if no specific asset |
| `annotator_id` | Your name or student ID |
| `market_relevant` | `true` / `false` – Does this post have potential to move the market of the mentioned asset? |
| `sentiment` | `bullish` / `bearish` / `neutral` |
| `sentiment_score` | From -1.0 (strongly bearish) to +1.0 (strongly bullish). Use 0 for neutral |
| `topic` | Main topic (e.g. Tesla, AI, Robotaxi, Dogecoin, Bitcoin, production, regulation, joke) |
| `impact_horizon` | `hours` / `days` / `unknown` |
| `ambiguous` | `true` if the post is hard to judge (sarcasm, joke, vague, mixed signals). Must be the string `"true"` or `"false"` |
| `notes` | Short explanation, especially if ambiguous |

## Three decision rules

### Case 1 — Direct asset mention
If the post clearly names or refers to TSLA, BTC-USD, or DOGE-USD:
- `market_relevant` = true
- Include the asset in `assets` with sentiment, score, and confidence
- Set `ambiguous` = "false" unless the direction is genuinely unclear

### Case 2 — Linked Musk company
If a Musk company (Tesla, SpaceX, Starlink, xAI, X/Twitter, etc.) is **explicitly linked** to one of the three assets:
- `market_relevant` = true
- Include the linked asset
- Briefly note the link in notes if needed
- Set `ambiguous` = "false" if the link is clear

### Case 3 — Ecosystem only (no asset)
If the post only mentions SpaceX, Starlink, Starship, xAI, Grok, or X/Twitter and does **not** name or clearly link one of the three assets:
- `market_relevant` = false
- `assets` = []
- `topics` = ["musk_ecosystem"]
- `ambiguous` = "true"

## Labelling Rules

### 1. Bullish
- Positive comments about the company/product/price
- Announcements of good news (new product, higher production, approval, etc.)
- Optimistic future statements that are likely to be taken seriously by the market

### 2. Bearish
- Criticism, problems, delays, accidents, investigations
- Negative comments about price or competitors that hurt the asset
- Statements that could reasonably be expected to push the price down

### 3. Neutral
- Pure jokes / memes with no clear directional opinion
- Factual statements without positive or negative implication
- Posts that mention the asset but have no price implication
- Ambiguous or mixed signals that cancel out

### 4. Special Cases
- **Sarcasm / jokes**: Usually mark as `neutral` + `ambiguous = true`, unless the market is very likely to take it seriously.
- **Multiple assets**: Create one entry per important asset in the `assets` list.
- **Replies**: Only label if the reply itself contains clear new information. Most replies should already be filtered out.
- **No clear asset**: Follow Case 3.

## Important Principles
- Label based on **expected market reaction**, not your personal opinion.
- Do **not** look at the stock/crypto price after the post while labelling.
- When unsure, set `ambiguous = true` and explain in `notes`.
- Be consistent. When in doubt, discuss with the group.
- `sentiment_score` must match the label:
  - bullish → (0, 1]
  - bearish → [-1, 0)
  - neutral → exactly 0
- If `market_relevant` is false, `assets` must be empty.