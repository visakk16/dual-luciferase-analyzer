# Dual-Luciferase Reporter Assay Analyzer

A Streamlit app for analyzing Nano-Glo® Dual-Luciferase® 384-well plate reader
exports.

## What it does (v1)

- Upload an Excel export containing two stacked 384-well plate blocks:
  1. **NanoLuc®** data (first block)
  2. **Luc2 / Firefly** data (second block, directly underneath)
- Each block is auto-detected by looking for row labels A–P in column A, so it
  doesn't matter exactly which rows they land on in the sheet.
- Computes **Luc2 / NanoLuc** for every well (the normalized reporter ratio).
- Shows the ratio plate, plus both raw plates, as color-coded 16×24 grids.
- The replicate grouping grid **starts pre-filled with the lab's standard
  triplicate layout** (32 groups of 3 adjacent wells, on rows A, C, E, G, I,
  K, M, O — columns 1-3, 5-7, 9-11, 13-15 in each). You can freely edit,
  rename, clear, or reset it back to this default at any time.
- Wells sharing the same group label are averaged together into mean, std,
  SEM, and n.
- Download the ratio, both raw plates, and the group summary as a single
  Excel file.

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Next steps / ideas for later iterations

- Dose-response curve fitting off the group averages
- Flagging/excluding low-signal or outlier wells
- Saving/reloading a plate map layout so you don't have to re-label it every run
- Support for 96-well plates in addition to 384-well
