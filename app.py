import io
import re
import string

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Dual-Luciferase Assay Analyzer", layout="wide")

ROW_LETTERS_384 = list(string.ascii_uppercase[:16])  # A-P
N_COLS_384 = 24

# Default triplicate layout for a standard 384-well NanoDLR plate, derived from
# the lab's group-locations reference sheet. Odd rows (A, C, E, G, I, K, M, O)
# each hold 4 triplicate groups (columns 1-3, 5-7, 9-11, 13-15); column 4/8/12/16
# and even rows are left ungrouped (blank) by default. Columns 17-24 are unused.
# Users can freely edit this in the app - it's just a starting point.
DEFAULT_GROUP_MAP_384 = {
    "A": ["Group 1", "Group 1", "Group 1", "", "Group 9", "Group 9", "Group 9", "", "Group 17", "Group 17", "Group 17", "", "Group 25", "Group 25", "Group 25", "", "", "", "", "", "", "", "", ""],
    "B": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    "C": ["Group 2", "Group 2", "Group 2", "", "Group 10", "Group 10", "Group 10", "", "Group 18", "Group 18", "Group 18", "", "Group 26", "Group 26", "Group 26", "", "", "", "", "", "", "", "", ""],
    "D": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    "E": ["Group 3", "Group 3", "Group 3", "", "Group 11", "Group 11", "Group 11", "", "Group 19", "Group 19", "Group 19", "", "Group 27", "Group 27", "Group 27", "", "", "", "", "", "", "", "", ""],
    "F": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    "G": ["Group 4", "Group 4", "Group 4", "", "Group 12", "Group 12", "Group 12", "", "Group 20", "Group 20", "Group 20", "", "Group 28", "Group 28", "Group 28", "", "", "", "", "", "", "", "", ""],
    "H": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    "I": ["Group 5", "Group 5", "Group 5", "", "Group 13", "Group 13", "Group 13", "", "Group 21", "Group 21", "Group 21", "", "Group 29", "Group 29", "Group 29", "", "", "", "", "", "", "", "", ""],
    "J": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    "K": ["Group 6", "Group 6", "Group 6", "", "Group 14", "Group 14", "Group 14", "", "Group 22", "Group 22", "Group 22", "", "Group 30", "Group 30", "Group 30", "", "", "", "", "", "", "", "", ""],
    "L": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    "M": ["Group 7", "Group 7", "Group 7", "", "Group 15", "Group 15", "Group 15", "", "Group 23", "Group 23", "Group 23", "", "Group 31", "Group 31", "Group 31", "", "", "", "", "", "", "", "", ""],
    "N": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    "O": ["Group 8", "Group 8", "Group 8", "", "Group 16", "Group 16", "Group 16", "", "Group 24", "Group 24", "Group 24", "", "Group 32", "Group 32", "Group 32", "", "", "", "", "", "", "", "", ""],
    "P": ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
}


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def load_raw_grid(file) -> pd.DataFrame:
    """Read the uploaded file into a raw (no header) DataFrame of strings/values."""
    return pd.read_excel(file, header=None, engine="openpyxl")


def find_plate_blocks(raw: pd.DataFrame, n_cols: int = N_COLS_384):
    """
    Locate consecutive-row blocks whose first column is a plate row letter
    (A, B, C, ...). Each block found is returned as a numeric DataFrame
    (rows = letters found, columns = 1..n_cols) plus the letters, in the
    order they appear top-to-bottom in the sheet.
    """
    col0 = raw.iloc[:, 0].astype(str).str.strip()
    is_row_label = col0.str.fullmatch(r"[A-Za-z]{1,2}")

    blocks = []
    current_rows = []
    current_letters = []

    def flush():
        if current_rows:
            block_df = pd.DataFrame(
                current_rows, index=current_letters, columns=range(1, n_cols + 1)
            )
            blocks.append(block_df)

    for idx in raw.index:
        if is_row_label.loc[idx]:
            letter = col0.loc[idx]
            values = raw.iloc[idx, 1 : n_cols + 1].tolist()
            # pad/truncate defensively
            values = (values + [np.nan] * n_cols)[:n_cols]
            values = [pd.to_numeric(v, errors="coerce") for v in values]
            current_rows.append(values)
            current_letters.append(letter)
        else:
            flush()
            current_rows, current_letters = [], []
    flush()

    return blocks


def extract_two_plates(raw: pd.DataFrame):
    blocks = find_plate_blocks(raw)
    # Keep only blocks that look like a full (or near-full) plate block
    blocks = [b for b in blocks if len(b) >= 8]

    if len(blocks) < 2:
        raise ValueError(
            f"Expected to find 2 plate data blocks (NanoLuc, then Luc2/Firefly), "
            f"but only found {len(blocks)}. Check that the sheet has the two "
            f"384-well blocks stacked vertically, each with row letters A-P in "
            f"column A."
        )

    nanoluc = blocks[0]
    luc2 = blocks[1]
    return nanoluc, luc2


def compute_ratio(nanoluc: pd.DataFrame, luc2: pd.DataFrame) -> pd.DataFrame:
    """Luc2 (firefly) / NanoLuc, aligned on shared rows/columns."""
    rows = [r for r in nanoluc.index if r in luc2.index]
    cols = [c for c in nanoluc.columns if c in luc2.columns]
    a = nanoluc.loc[rows, cols].astype(float)
    b = luc2.loc[rows, cols].astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = b / a
    ratio = ratio.replace([np.inf, -np.inf], np.nan)
    return ratio


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------
def style_plate(df: pd.DataFrame, fmt="{:,.0f}", cmap="Blues"):
    return df.style.format(fmt, na_rep="—").background_gradient(cmap=cmap, axis=None)


def to_excel_bytes(sheets: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name[:31])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Replicate grouping / averaging
# ---------------------------------------------------------------------------
def blank_group_map(rows, cols) -> pd.DataFrame:
    return pd.DataFrame("", index=rows, columns=cols)


def default_group_map(rows, cols) -> pd.DataFrame:
    """The lab's standard triplicate layout, reindexed to whatever rows/columns
    were actually detected in the uploaded plate (extra rows/cols are left
    blank; missing ones are simply not included)."""
    base = pd.DataFrame(DEFAULT_GROUP_MAP_384).T
    base.columns = range(1, base.shape[1] + 1)
    return base.reindex(index=rows, columns=cols, fill_value="")


def autofill_by_columns(rows, cols, cols_per_group: int) -> pd.DataFrame:
    """Every row gets the same column grouping: cols_per_group columns per
    group, labeled Group 1, Group 2, ... left to right, repeated identically
    down every row."""
    labels_per_row = []
    group_num = 0
    for i, _ in enumerate(cols):
        if i % cols_per_group == 0:
            group_num += 1
        labels_per_row.append(f"Group {group_num}")
    data = [labels_per_row for _ in rows]
    return pd.DataFrame(data, index=rows, columns=cols)


def summarize_groups(value_plate: pd.DataFrame, group_map: pd.DataFrame) -> pd.DataFrame:
    """Melt the value plate + group map into long form and compute
    n, mean, std, and SEM per non-blank group label."""
    long = pd.DataFrame(
        {
            "row": np.repeat(value_plate.index.values, len(value_plate.columns)),
            "col": list(value_plate.columns) * len(value_plate.index),
            "value": value_plate.values.flatten(),
            "group": group_map.reindex(index=value_plate.index, columns=value_plate.columns)
            .values.flatten(),
        }
    )
    long["well"] = long["row"].astype(str) + long["col"].astype(str)
    long["group"] = long["group"].astype(str).str.strip()
    long = long[(long["group"] != "") & (long["group"].str.lower() != "nan")]
    long = long.dropna(subset=["value"])

    if long.empty:
        return pd.DataFrame(columns=["group", "n", "mean", "std", "sem", "wells"])

    def _agg(g):
        n = g["value"].count()
        mean = g["value"].mean()
        std = g["value"].std(ddof=1) if n > 1 else np.nan
        sem = std / np.sqrt(n) if n > 1 else np.nan
        wells = ", ".join(g["well"])
        return pd.Series({"n": n, "mean": mean, "std": std, "sem": sem, "wells": wells})

    summary = long.groupby("group", sort=False).apply(_agg).reset_index()
    return summary


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
st.title("Dual-Luciferase Reporter Assay Analyzer")
st.caption(
    "Upload a plate-reader export with two stacked 384-well blocks "
    "(NanoLuc® first, then Luc2/Firefly second). The app divides "
    "Luc2 / NanoLuc for every well."
)

uploaded = st.file_uploader("Upload plate reader Excel file (.xlsx)", type=["xlsx"])

if uploaded is not None:
    try:
        raw = load_raw_grid(uploaded)
        nanoluc, luc2 = extract_two_plates(raw)
        ratio = compute_ratio(nanoluc, luc2)
    except Exception as e:
        st.error(str(e))
        st.stop()

    st.success(
        f"Found two {nanoluc.shape[0]}×{nanoluc.shape[1]} plate blocks. "
        "Computed Luc2 / NanoLuc ratio below."
    )

    tab1, tab2, tab3 = st.tabs(["Ratio (Luc2 / NanoLuc)", "NanoLuc (raw)", "Luc2 (raw)"])

    with tab1:
        st.subheader("Luc2 / NanoLuc ratio")
        st.dataframe(style_plate(ratio, fmt="{:.3f}", cmap="RdYlGn"), width="stretch")

    with tab2:
        st.subheader("NanoLuc® (Plate 1, raw luminescence)")
        st.dataframe(style_plate(nanoluc), width="stretch")

    with tab3:
        st.subheader("Luc2 / Firefly (Plate 2, raw luminescence)")
        st.dataframe(style_plate(luc2), width="stretch")

    st.divider()

    # -----------------------------------------------------------------
    # Replicate grouping
    # -----------------------------------------------------------------
    st.header("Group replicates & compute averages ± SEM")
    st.caption(
        "Label which wells belong to the same sample/condition below — you "
        "decide the layout. Type a group name into any well; wells sharing "
        "the same name are averaged together. Leave a well blank to exclude "
        "it. You can type directly into the grid, or paste in from Excel. "
        "The grid starts pre-filled with the lab's standard triplicate "
        "layout — edit or reset it as needed."
    )

    rows, cols = list(ratio.index), list(ratio.columns)

    # Keep the editable grouping in session state so edits persist across reruns,
    # keyed to the current file so a new upload resets it.
    file_key = getattr(uploaded, "name", "current") + str(uploaded.size)
    if st.session_state.get("_group_map_key") != file_key:
        st.session_state["_group_map"] = default_group_map(rows, cols)
        st.session_state["_group_map_key"] = file_key

    with st.expander("Quick-fill by columns (optional starting point)"):
        c1, c2 = st.columns([2, 1])
        with c1:
            cols_per_group = st.number_input(
                "Columns per group", min_value=1, max_value=len(cols), value=3, step=1
            )
        with c2:
            st.write("")
            st.write("")
            if st.button("Auto-fill groups"):
                st.session_state["_group_map"] = autofill_by_columns(
                    rows, cols, int(cols_per_group)
                )
        if st.button("Clear all labels"):
            st.session_state["_group_map"] = blank_group_map(rows, cols)
        if st.button("Reset to default triplicate layout"):
            st.session_state["_group_map"] = default_group_map(rows, cols)

    edited_group_map = st.data_editor(
        st.session_state["_group_map"],
        width="stretch",
        key=f"group_editor_{file_key}",
    )
    st.session_state["_group_map"] = edited_group_map

    summary = summarize_groups(ratio, edited_group_map)

    if summary.empty:
        st.info("Label some wells above to see group averages ± SEM here.")
    else:
        st.subheader("Group averages (Luc2 / NanoLuc ratio)")
        display_summary = summary.copy()
        for c in ["mean", "std", "sem"]:
            display_summary[c] = display_summary[c].round(4)
        st.dataframe(display_summary, width="stretch")

    st.divider()
    sheets = {"Ratio_Luc2_over_NanoLuc": ratio, "NanoLuc_raw": nanoluc, "Luc2_raw": luc2}
    if not summary.empty:
        sheets["Group_Summary"] = summary.set_index("group")
    excel_bytes = to_excel_bytes(sheets)
    st.download_button(
        "Download results (Excel)",
        data=excel_bytes,
        file_name="dual_luciferase_ratio_results.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
else:
    st.info("Upload a file to begin.")
