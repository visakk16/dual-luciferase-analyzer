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
- **Replicate grouping is fully up to you at run time:** an editable 16×24
  plate-map grid lets you type (or paste) a group/sample name into any well.
  Wells sharing the same label are averaged together into mean, std, SEM,
  and n. An optional "auto-fill by columns" helper can pre-fill a simple
  repeating column pattern as a starting point, which you can then rename or
  edit freely.
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
