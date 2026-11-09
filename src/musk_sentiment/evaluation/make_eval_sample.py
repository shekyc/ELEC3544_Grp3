"""
Build the 150-post evaluation sample (50 dev + 100 test) for annotation.

Run from the repository root:
    python scripts/make_eval_sample.py

Output: annotations/eval_sample.csv  (MASTER file - do not give this to annotators)
The script refuses to overwrite an existing sample unless you pass --force,
so the sample stays locked once it has been committed.
"""
import sys
from pathlib import Path

import pandas as pd

# ---------- SETTINGS: edit these to match your real files ----------
ROOT = Path(__file__).resolve().parent.parent.parent.parent
POSTS_FILE = ROOT / "data/processed/posts/posts.json"
OUT_FILE = ROOT / "annotations/eval_sample.csv"

ID_COL = "post_id"            # column with the unique post ID
TIME_COL = "created_at"    # column with the post time
TEXT_COL = "text"             # column with the post text

START = "2023-01-01"          # start of the window (use the group's agreed window)
END = "2025-04-13"            # end of the window
SEED = 42                     # fixed seed so anyone can reproduce the sample
N_PER_STRATUM = 75            # 75 random + 75 keyword = 150 posts
DEV_PER_STRATUM = 25          # 25 + 25 = 50 dev; the remaining 100 are test

KEYWORDS = (r"tesla|tsla|fsd|cybertruck|robotaxi|optimus|doge|bitcoin|btc|"
            r"crypto|xai|spacex|starlink|stock|shares")
# --------------------------------------------------------------------

if OUT_FILE.exists() and "--force" not in sys.argv:
    sys.exit(f"{OUT_FILE} already exists. The sample is locked; use --force only if the group agrees.")

# 1. Load and prepare the pool
df = pd.read_json(POSTS_FILE)
df[TIME_COL] = pd.to_datetime(df[TIME_COL], utc=True)
df = df.drop_duplicates(subset=ID_COL)
df = df[df[TIME_COL].between(pd.Timestamp(START, tz="UTC"), pd.Timestamp(END, tz="UTC"))]
df = df[df[TEXT_COL].fillna("").str.strip().str.len() > 10]
print(f"Pool: {len(df)} posts between {START} and {END}")

# 2. Flag keyword posts
no_doge = df[TEXT_COL].str.replace(r"@doge\b|department of government efficiency", "", case=False, regex=True)
df["is_kw"] = no_doge.str.contains(KEYWORDS, case=False, regex=True)
print(f"Keyword posts in pool: {df['is_kw'].sum()}")
if df["is_kw"].sum() < N_PER_STRATUM * 2:
    sys.exit("Not enough keyword posts to sample from; widen the window or reduce N_PER_STRATUM.")

# 3. Random stratum, then keyword stratum (no overlap between the two)
rand = df.sample(N_PER_STRATUM, random_state=SEED).assign(stratum="random")
kw_pool = df[df["is_kw"] & ~df.index.isin(rand.index)]
kw = kw_pool.sample(N_PER_STRATUM, random_state=SEED).assign(stratum="keyword")
sample = pd.concat([rand, kw])

# 4. Split into dev / test, keeping the same random/keyword mix in each
dev = pd.concat([g.sample(DEV_PER_STRATUM, random_state=SEED)
                 for _, g in sample.groupby("stratum")]).assign(split="dev")
test = sample.drop(dev.index).assign(split="test")
out = pd.concat([dev, test]).sample(frac=1, random_state=SEED)

# 5. Sanity checks
print("\nCounts by split and stratum:")
print(pd.crosstab(out["split"], out["stratum"]))
print("\nPosts per quarter:")
print(out[TIME_COL].dt.tz_localize(None).dt.to_period("Q").value_counts().sort_index())

# 6. Save
OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
out[[ID_COL, TIME_COL, TEXT_COL, "stratum", "split"]].to_csv(OUT_FILE, index=False)
print(f"\nSaved {len(out)} posts to {OUT_FILE}")