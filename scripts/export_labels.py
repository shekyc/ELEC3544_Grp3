import pandas as pd

# for split in ("dev" , "test"):
#     src = f"annotations/templates/{split}_yik_yu_hang.xlsx"
#     dst = f"annotations/final_labels_{split}.csv"
#     try:
#         df = pd.read_excel(src, dtype={"post_id": str})
#     except FileNotFoundError:
#         print(f"Skipping {split}: {src} not found")
#         continue
#     df.to_csv(dst, index=False)
#     print(f"Saved {len(df)} rows to {dst}")

src = f"annotations/templates/dev_yik_yu_hang.xlsx"
dst = f"annotations/final_labels_dev_yik_yu_hang.xlsx"
try:
  df = pd.read_excel(src, dtype={"post_id": str})
except FileNotFoundError:
  print(f"Skipping dev: dev not found")
df.to_csv(dst, index=False)
print(f"Saved {len(df)} rows to {dst}")