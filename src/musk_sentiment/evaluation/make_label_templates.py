"""
Create blank annotation templates (.xlsx) from the locked evaluation sample.
Single annotator: one person labels all 150 posts (50 dev + 100 test).

Run from the repository root:
    python scripts/make_label_templates.py

Outputs (annotations/templates/):
    dev_<name>.xlsx   (50 posts)
    test_<name>.xlsx  (100 posts)

The script refuses to overwrite existing templates (so filled-in labels are never
lost) unless --force.
"""

import sys
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

# ---------- SETTINGS: edit to match your repo and docs/ANNOTATION.md ----------
ROOT = Path(__file__).resolve().parent.parent.parent.parent
SAMPLE_FILE = ROOT / "annotations/eval_sample_1_oneline.csv"  # the locked one-line sample
OUT_DIR = ROOT / "annotations/templates"

ANNOTATOR = "yik_yu_hang"  # used in the file names, e.g. dev_yik_yu_hang.xlsx
SEED = 42

ID_COL, TEXT_COL, SPLIT_COL = "post_id", "text", "split"

# Label columns, in order. REPLACE these with the exact fields in docs/ANNOTATION.md,
# and keep the same names/order as the pilot label CSV so results can be compared later.
LABEL_COLS = [
    "market_relevant",
    "assets",
    "sentiment",
    "sentiment_score",
    "ambiguous",
    "topic",
    "notes",
]

# Optional dropdowns (column -> allowed values). Must match the guidelines' wording exactly.
# Delete a line (or leave the dict empty) for free-text columns.
DROPDOWNS = {
    "market_relevant": ["yes", "no"],
    "sentiment": ["bullish", "bearish", "neutral"],
    "ambiguous": ["yes", "no"],
}
# -------------------------------------------------------------------------------

if OUT_DIR.exists() and any(OUT_DIR.glob("*.xlsx")) and "--force" not in sys.argv:
    sys.exit(
        f"Templates already exist in {OUT_DIR}. "
        "Not overwriting (labels could be lost). "
        "Use --force only if you have not started."
    )

df = pd.read_csv(SAMPLE_FILE, dtype={ID_COL: str})
assert len(df) == 150 and df[ID_COL].is_unique, "Expected 150 unique posts."
counts = df[SPLIT_COL].value_counts().to_dict()
assert counts == {"test": 100, "dev": 50}, f"Expected 50 dev / 100 test, got {counts}."

OUT_DIR.mkdir(parents=True, exist_ok=True)
header_fill = PatternFill("solid", fgColor="DDEBF7")

for split in ("dev", "test"):
    part = df[df[SPLIT_COL] == split].sample(frac=1, random_state=SEED)  # random order
    wb = Workbook()
    ws = wb.active
    ws.title = split
    ws.append([ID_COL, TEXT_COL] + LABEL_COLS)
    for c in ws[1]:
        c.font, c.fill = Font(bold=True), header_fill
    for pid, text in zip(part[ID_COL], part[TEXT_COL], strict=True):
        ws.append([str(pid), text] + [None] * len(LABEL_COLS))
        ws.cell(row=ws.max_row, column=1).number_format = "@"  # keep the 19-digit ID as text
        ws.cell(row=ws.max_row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 80
    for j, col in enumerate(LABEL_COLS, start=3):
        letter = ws.cell(row=1, column=j).column_letter
        ws.column_dimensions[letter].width = 40 if col in ("notes", "topic", "assets") else 16
        if col in DROPDOWNS:
            dv = DataValidation(
                type="list", formula1='"' + ",".join(DROPDOWNS[col]) + '"', allow_blank=True
            )
            ws.add_data_validation(dv)
            dv.add(f"{letter}2:{letter}{ws.max_row}")
    ws.freeze_panes = "C2"
    wb.save(OUT_DIR / f"{split}_{ANNOTATOR}.xlsx")
    print(f"{split}_{ANNOTATOR}.xlsx: {len(part)} posts")

print(f"Saved to {OUT_DIR}")
