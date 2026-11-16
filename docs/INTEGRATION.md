# Integration audit — 2026-11-16

Created `sheky/merge` from local `main` (e496222) after fetching all remotes. Remote main b763683
contains the old pilot/guidelines changes; it was reviewed, not wholesale merged.
Reviewed Tansy e769999 and Cyrus d889149. Original proposal PDF is not present at its previously
supplied path in this session; scope is preserved from the supplied master request and methodology.

| Source work | Decision | Reason |
|---|---|---|
| Tansy Kaggle column map | Copy unchanged | Useful schema mapping, no data or date restriction |
| Tansy financial sentiment/ambiguity guidance | Adapt into v5 and annotation rules | Useful distinctions; remove three-asset restriction and unsupported company exposure |
| Cyrus random + keyword sampling and dev/test design | Reimplement with string IDs and quarter coverage | Existing pandas JSON inference loses IDs; old dates and fixed keywords are unsuitable |
| Old 50/150 manual labels | Do not import into study | Outside 2020–2021; some IDs damaged, inconsistent vocabulary; source branches preserve human work |
| 8,991 predictions and evaluation predictions | Do not copy | Wrong corpus period, old prompt and restricted universe; not validated for revised scope |
| Tansy's 679-post extract | Do not use as corpus | Partial two-year extract; original CSV can reproduce a better audited cohort |
| Workbook templates, Excel lock file, duplicate exports | Do not copy | No advantage over the new exact-ID annotation workflow |

## Source reconciliation

Uploaded original `all_musk_posts.csv`: 55,099 rows. Every ID in the 50-post pilot and 679-post
extract matches this raw file. Cyrus's 150-row sample has only 10 exact-ID matches; 89 other rows
have unique exact-text matches with different IDs. After HTML-entity/whitespace normalization,
148/150 rows have a unique text candidate; the other two have repeated text candidates. Thus all
150 sampled texts are represented in this upload. This supports a transformation/ID-rounding
explanation, not a demonstrated change of dataset. Text matching is diagnostic, not ID repair.
The sample generator uses `pd.read_json` without preserving ID strings. No rounded ID is trusted.

The old README conversion filled missing reply/repost fields with false and assigned the author
as Elon Musk. The replacement verifies the status URL ID/author and preserves unknown flags.
Actual new import: 14,018 original posts across the full archive; 828 unknown-status exclusions,
40,124 reply/repost exclusions and 129 other-author exclusions (categories are evaluated in importer
order). **1,234 posts** fall in 2020–2021; every month is represented. Archive completeness remains
unproven. Uploaded raw CSV, snapshots, labels and generated artifacts are Git-ignored.

Local evidence: `data/processed/posts_full/posts_quality.json`, `data/processed/study/quality.json`,
`data/processed/study/branch_source_audit.json`. Source hashes are recorded there, not inferred
from a dataset title. Neither old branch is changed or deleted.
