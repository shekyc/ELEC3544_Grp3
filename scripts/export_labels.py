import pandas as pd

src = "annotations/templates/test_yik_yu_hang.xlsx"
dst = "annotations/final_labels_test_yik_yu_hang.csv"
try:
    df = pd.read_excel(src, dtype={"post_id": str})
except FileNotFoundError:
    print("Skipping test: test not found")
df.to_csv(dst, index=False)
print(f"Saved {len(df)} rows to {dst}")
