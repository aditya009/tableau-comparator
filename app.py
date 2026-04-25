import streamlit as st
import pandas as pd
import numpy as np
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io
import csv
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Tableau Report Comparator",
    page_icon="⇄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Overall font */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #1e2130;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        padding: 1rem 1.25rem;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Compare button */
    div.stButton > button {
        width: 100%;
        background: #4f7cff;
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.65rem 2rem;
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.3px;
        transition: all 0.15s;
    }
    div.stButton > button:hover {
        background: #3d63d4;
        box-shadow: 0 4px 20px rgba(79,124,255,0.4);
        transform: translateY(-1px);
    }

    /* Diff cell colours in dataframe */
    .diff-modified  { background-color: rgba(255,92,92,0.18)  !important; color: #ff5c5c !important; font-weight: 600 !important; }
    .diff-added     { background-color: rgba(54,201,126,0.15) !important; color: #36c97e !important; font-weight: 600 !important; }
    .diff-removed   { background-color: rgba(240,168,48,0.15) !important; color: #f0a830 !important; font-weight: 600 !important; }
    .diff-match     { color: #8b8fa8 !important; }

    /* Upload boxes */
    [data-testid="stFileUploader"] {
        border: 1.5px dashed rgba(255,255,255,0.15);
        border-radius: 12px;
        padding: 0.5rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #1a1d27;
        border-right: 1px solid rgba(255,255,255,0.06);
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        padding: 6px 18px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)


# ── Helper functions ──────────────────────────────────────────────────────────

def load_excel(file) -> dict[str, pd.DataFrame]:
    """Read all sheets from an uploaded Excel/CSV file."""
    name = file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(file, dtype=str, keep_default_na=False)
        return {"Sheet1": df}
    else:
        xl = pd.ExcelFile(file, engine="openpyxl")
        return {
            sheet: xl.parse(sheet, dtype=str, keep_default_na=False)
            for sheet in xl.sheet_names
        }


def normalise(val: str, ignore_case: bool, trim: bool) -> str:
    s = str(val) if val is not None else ""
    if trim:
        s = s.strip()
    if ignore_case:
        s = s.lower()
    return s


def numeric_close(a: str, b: str, tol: float) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except (ValueError, TypeError):
        return False


def compare_sheets(
    df_a: pd.DataFrame,
    df_b: pd.DataFrame,
    ignore_case: bool,
    trim: bool,
    tol: float,
) -> dict:
    """
    Returns a dict with:
      - result_df  : DataFrame showing Source | Output | Status for each column
      - stats      : {modified, added_rows, removed_rows, matched}
      - diff_mask  : boolean DataFrame True where cells differ
    """
    # Align to same shape
    rows = max(len(df_a), len(df_b))
    cols_a = set(df_a.columns)
    cols_b = set(df_b.columns)
    all_cols = list(df_a.columns) + [c for c in df_b.columns if c not in cols_a]

    df_a = df_a.reindex(index=range(rows), columns=all_cols, fill_value="")
    df_b = df_b.reindex(index=range(rows), columns=all_cols, fill_value="")

    df_a = df_a.fillna("").astype(str)
    df_b = df_b.fillna("").astype(str)

    status_df  = pd.DataFrame(index=range(rows), columns=all_cols, dtype=str)
    diff_mask  = pd.DataFrame(False, index=range(rows), columns=all_cols)

    modified = added = removed = matched = 0

    for col in all_cols:
        col_in_a = col in cols_a
        col_in_b = col in cols_b
        for r in range(rows):
            va = df_a.at[r, col]
            vb = df_b.at[r, col]
            row_in_a = r < len(df_a)
            row_in_b = r < len(df_b)

            if col_in_a and not col_in_b:
                status = "removed"; removed += 1
            elif not col_in_a and col_in_b:
                status = "added"; added += 1
            else:
                na = normalise(va, ignore_case, trim)
                nb = normalise(vb, ignore_case, trim)
                if na == nb or (tol > 0 and numeric_close(na, nb, tol)):
                    status = "match"; matched += 1
                else:
                    status = "modified"; modified += 1
                    diff_mask.at[r, col] = True

            status_df.at[r, col] = status
            if status != "match":
                diff_mask.at[r, col] = True

    return {
        "df_a": df_a,
        "df_b": df_b,
        "status_df": status_df,
        "diff_mask": diff_mask,
        "stats": {
            "modified": modified,
            "added": added,
            "removed": removed,
            "matched": matched,
        },
        "columns": all_cols,
    }


def build_display_df(cmp: dict, diff_only: bool) -> pd.DataFrame:
    """Build a flat display DataFrame: col_Source | col_Output columns."""
    cols = cmp["columns"]
    df_a = cmp["df_a"]
    df_b = cmp["df_b"]
    status_df = cmp["status_df"]
    diff_mask = cmp["diff_mask"]

    out_cols = {}
    for col in cols:
        out_cols[f"{col} ▸ Source"] = df_a[col].tolist()
        out_cols[f"{col} ▸ Output"] = df_b[col].tolist()
        out_cols[f"{col} ▸ Status"] = status_df[col].tolist()

    display = pd.DataFrame(out_cols)
    display.index = display.index + 1  # 1-based row numbers
    display.index.name = "Row"

    if diff_only:
        has_diff = diff_mask.any(axis=1)
        display = display[has_diff.values]

    return display


def style_display(display: pd.DataFrame) -> pd.DataFrame.style:
    """Apply cell-level background colours based on Status columns."""
    status_cols = [c for c in display.columns if c.endswith("▸ Status")]

    def colour_row(row):
        styles = [""] * len(row)
        for sc in status_cols:
            if sc not in row.index:
                continue
            status = row[sc]
            base = sc.replace(" ▸ Status", "")
            src_col = f"{base} ▸ Source"
            out_col = f"{base} ▸ Output"
            if status == "modified":
                colour = "background-color: rgba(255,92,92,0.18); color: #c0392b; font-weight: 600"
            elif status == "added":
                colour = "background-color: rgba(54,201,126,0.15); color: #1e8449; font-weight: 600"
            elif status == "removed":
                colour = "background-color: rgba(240,168,48,0.15); color: #b7770d; font-weight: 600"
            else:
                colour = "color: #555"
            for tc in [src_col, out_col, sc]:
                if tc in row.index:
                    idx = list(row.index).index(tc)
                    styles[idx] = colour
        return styles

    return display.style.apply(colour_row, axis=1)


def export_to_excel(cmp_results: dict) -> bytes:
    """
    Export all sheet comparisons to a formatted Excel workbook.
    Green = match, Red = modified, Orange = added/removed.
    """
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    fill_match    = PatternFill("solid", fgColor="D5F5E3")
    fill_modified = PatternFill("solid", fgColor="FADBD8")
    fill_added    = PatternFill("solid", fgColor="FEF9E7")
    fill_removed  = PatternFill("solid", fgColor="FDEBD0")
    fill_header   = PatternFill("solid", fgColor="2C3E50")

    hdr_font  = Font(bold=True, color="FFFFFF", name="Calibri")
    bold_font = Font(bold=True, name="Calibri")
    norm_font = Font(name="Calibri")
    center    = Alignment(horizontal="center", vertical="center")
    thin = Border(
        left=Side(style="thin", color="CCCCCC"),
        right=Side(style="thin", color="CCCCCC"),
        top=Side(style="thin", color="CCCCCC"),
        bottom=Side(style="thin", color="CCCCCC"),
    )

    status_fill = {
        "match": fill_match,
        "modified": fill_modified,
        "added": fill_added,
        "removed": fill_removed,
    }

    for sheet_name, cmp in cmp_results.items():
        ws = wb.create_sheet(title=sheet_name[:31])
        cols = cmp["columns"]

        # Header row 1 — column names spanning Source/Output
        ws.cell(1, 1, "Row").fill = fill_header
        ws.cell(1, 1).font = hdr_font
        ws.cell(1, 1).alignment = center

        col_offset = 2
        for col in cols:
            src_cell = ws.cell(1, col_offset, f"{col}")
            src_cell.fill = fill_header
            src_cell.font = hdr_font
            src_cell.alignment = center
            ws.merge_cells(
                start_row=1, start_column=col_offset,
                end_row=1, end_column=col_offset + 1
            )
            col_offset += 2

        # Header row 2 — Source / Output sub-headers
        ws.cell(2, 1, "").fill = fill_header
        col_offset = 2
        for col in cols:
            for label in ["Source", "Output"]:
                c = ws.cell(2, col_offset, label)
                c.fill = PatternFill("solid", fgColor="3D5166")
                c.font = Font(bold=True, color="FFFFFF", name="Calibri", size=9)
                c.alignment = center
                col_offset += 1

        ws.freeze_panes = "B3"

        # Data rows
        df_a = cmp["df_a"]
        df_b = cmp["df_b"]
        status_df = cmp["status_df"]

        for r_idx, r in enumerate(range(len(df_a))):
            excel_row = r_idx + 3
            ws.cell(excel_row, 1, r + 1).alignment = center
            ws.cell(excel_row, 1).border = thin

            col_offset = 2
            for col in cols:
                status = status_df.at[r, col]
                fill   = status_fill.get(status, fill_match)
                va     = df_a.at[r, col]
                vb     = df_b.at[r, col]

                src_cell = ws.cell(excel_row, col_offset, va)
                out_cell = ws.cell(excel_row, col_offset + 1, vb)
                for cell in [src_cell, out_cell]:
                    cell.fill = fill
                    cell.font = bold_font if status != "match" else norm_font
                    cell.border = thin
                col_offset += 2

        # Auto-width columns
        for col_cells in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col_cells[0].column)
            for cell in col_cells:
                try:
                    if cell.value:
                        max_len = max(max_len, len(str(cell.value)))
                except:
                    pass
            ws.column_dimensions[col_letter].width = min(max_len + 4, 40)

        # Summary sheet
    summary_ws = wb.create_sheet("Summary", 0)
    summary_ws.append(["Sheet", "Modified Cells", "Added Cells", "Removed Cells", "Matching Cells", "Total Differences"])
    for cell in summary_ws[1]:
        cell.fill = fill_header
        cell.font = hdr_font
        cell.alignment = center

    for sheet_name, cmp in cmp_results.items():
        s = cmp["stats"]
        total_diff = s["modified"] + s["added"] + s["removed"]
        row = [sheet_name, s["modified"], s["added"], s["removed"], s["matched"], total_diff]
        summary_ws.append(row)

    for col_cells in summary_ws.columns:
        max_len = max((len(str(c.value or "")) for c in col_cells), default=10)
        summary_ws.column_dimensions[get_column_letter(col_cells[0].column)].width = max_len + 4

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()


def export_to_csv(cmp: dict) -> str:
    """Export diff rows only to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    cols = cmp["columns"]
    writer.writerow(["Row"] + [f"{c} (Source)" for c in cols] + [f"{c} (Output)" for c in cols] + [f"{c} (Status)" for c in cols])
    df_a = cmp["df_a"]
    df_b = cmp["df_b"]
    status_df = cmp["status_df"]
    diff_mask = cmp["diff_mask"]
    for r in range(len(df_a)):
        if diff_mask.iloc[r].any():
            row = [r + 1]
            row += [df_a.at[r, c] for c in cols]
            row += [df_b.at[r, c] for c in cols]
            row += [status_df.at[r, c] for c in cols]
            writer.writerow(row)
    return buf.getvalue()


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Comparison Settings")
    st.markdown("---")

    ignore_case = st.toggle("Ignore case", value=True,
        help="Treat 'ABC' and 'abc' as equal")

    trim_spaces = st.toggle("Trim whitespace", value=True,
        help="Ignore leading/trailing spaces")

    tol = st.select_slider(
        "Numeric tolerance",
        options=[0, 0.001, 0.01, 0.1, 1.0],
        value=0,
        help="Allow small numeric differences (useful for Tableau rounding)"
    )

    st.markdown("---")
    diff_only = st.toggle("Show differences only", value=False,
        help="Hide rows where all cells match")

    st.markdown("---")
    st.markdown("### 📋 About")
    st.markdown("""
Compare two Tableau Excel exports cell by cell.

**Colour legend:**
- 🔴 **Modified** — value changed
- 🟢 **Added** — only in output
- 🟡 **Removed** — only in source
- ⚪ **Match** — identical
    """)


# ── Main UI ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style='text-align:center; padding: 1.5rem 0 1rem;'>
  <h1 style='font-size:2.2rem; font-weight:800; letter-spacing:-1px; margin-bottom:0.4rem;'>
    ⇄ Tableau Report Comparator
  </h1>
  <p style='color:#8b8fa8; font-size:1rem; max-width:520px; margin:0 auto;'>
    Upload two Tableau Excel exports and instantly see every difference — line by line, column by column.
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ── File upload ───────────────────────────────────────────────────────────────
col1, col2 = st.columns(2)
with col1:
    st.markdown("#### 📄 Source / Expected")
    st.caption("Your baseline Tableau report")
    file_a = st.file_uploader("Source file", type=["xlsx","xls","csv"],
                               label_visibility="collapsed", key="file_a")
with col2:
    st.markdown("#### 📄 Output / Actual")
    st.caption("The generated report to verify")
    file_b = st.file_uploader("Output file", type=["xlsx","xls","csv"],
                               label_visibility="collapsed", key="file_b")

st.markdown("<br>", unsafe_allow_html=True)

# ── Compare button ────────────────────────────────────────────────────────────
col_btn, col_note = st.columns([1, 3])
with col_btn:
    compare_clicked = st.button("⇄  Compare Reports",
                                disabled=(file_a is None or file_b is None),
                                type="primary")
with col_note:
    if file_a is None or file_b is None:
        st.caption("⬆ Upload both files to enable comparison")
    else:
        st.caption(f"✅ **{file_a.name}**  vs  **{file_b.name}**  — ready to compare")


# ── Run comparison ────────────────────────────────────────────────────────────
if compare_clicked and file_a and file_b:
    with st.spinner("Reading files and comparing..."):
        try:
            sheets_a = load_excel(file_a)
            sheets_b = load_excel(file_b)
        except Exception as e:
            st.error(f"❌ Error reading files: {e}")
            st.stop()

        all_sheet_names = list(dict.fromkeys(list(sheets_a.keys()) + list(sheets_b.keys())))
        cmp_results = {}

        for sheet in all_sheet_names:
            da = sheets_a.get(sheet, pd.DataFrame())
            db = sheets_b.get(sheet, pd.DataFrame())
            cmp_results[sheet] = compare_sheets(da, db, ignore_case, trim_spaces, tol)

        st.session_state["cmp_results"] = cmp_results
        st.session_state["file_names"] = (file_a.name, file_b.name)
        st.session_state["settings"] = {
            "ignore_case": ignore_case,
            "trim_spaces": trim_spaces,
            "tol": tol,
            "diff_only": diff_only,
        }


# ── Show results ──────────────────────────────────────────────────────────────
if "cmp_results" in st.session_state:
    cmp_results = st.session_state["cmp_results"]
    fname_a, fname_b = st.session_state["file_names"]

    st.markdown("---")

    # ── Summary metrics ──
    total_modified = sum(c["stats"]["modified"] for c in cmp_results.values())
    total_added    = sum(c["stats"]["added"]    for c in cmp_results.values())
    total_removed  = sum(c["stats"]["removed"]  for c in cmp_results.values())
    total_matched  = sum(c["stats"]["matched"]  for c in cmp_results.values())
    total_diffs    = total_modified + total_added + total_removed

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("🔴 Modified",  f"{total_modified:,}")
    m2.metric("🟢 Added",     f"{total_added:,}")
    m3.metric("🟡 Removed",   f"{total_removed:,}")
    m4.metric("⚪ Matching",  f"{total_matched:,}")
    m5.metric("⚠️ Total diffs", f"{total_diffs:,}")

    st.markdown("<br>", unsafe_allow_html=True)

    if total_diffs == 0:
        st.success("🎉 **Perfect match!** Both reports are identical across all sheets and columns.")
    else:
        st.warning(f"⚠️ Found **{total_diffs:,}** difference(s) across **{len(cmp_results)}** sheet(s).")

    # ── Export buttons ──
    st.markdown("<br>", unsafe_allow_html=True)
    ex1, ex2, ex_spacer = st.columns([1, 1, 3])

    with ex1:
        excel_bytes = export_to_excel(cmp_results)
        st.download_button(
            "📥 Export to Excel (colour-coded)",
            data=excel_bytes,
            file_name=f"comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with ex2:
        # CSV export of first sheet diffs
        first_sheet = list(cmp_results.keys())[0]
        csv_str = export_to_csv(cmp_results[first_sheet])
        st.download_button(
            "📥 Export diffs to CSV",
            data=csv_str,
            file_name=f"diffs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

    st.markdown("---")

    # ── Per-sheet tabs ──
    if len(cmp_results) == 1:
        sheet_name = list(cmp_results.keys())[0]
        tabs = [st.container()]
        tab_map = {sheet_name: tabs[0]}
    else:
        tab_labels = []
        for s, c in cmp_results.items():
            d = c["stats"]["modified"] + c["stats"]["added"] + c["stats"]["removed"]
            label = f"{s}  🔴 {d}" if d > 0 else f"{s}  ✅"
            tab_labels.append(label)
        tabs = st.tabs(tab_labels)
        tab_map = dict(zip(cmp_results.keys(), tabs))

    for sheet_name, tab in tab_map.items():
        with tab:
            cmp = cmp_results[sheet_name]
            s = cmp["stats"]
            sh_diffs = s["modified"] + s["added"] + s["removed"]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Modified",  s["modified"])
            c2.metric("Added",     s["added"])
            c3.metric("Removed",   s["removed"])
            c4.metric("Matching",  s["matched"])

            st.markdown("<br>", unsafe_allow_html=True)

            if sh_diffs == 0:
                st.success(f"✅ Sheet **{sheet_name}** — no differences found.")
                continue

            display_df = build_display_df(cmp, diff_only=st.session_state["settings"]["diff_only"])

            # Hide Status columns for cleaner display
            visible_cols = [c for c in display_df.columns if "▸ Status" not in c]
            styled = style_display(display_df[visible_cols + [c for c in display_df.columns if "▸ Status" in c]])

            # Show only visible columns
            st.dataframe(
                styled.hide(axis="columns", subset=[c for c in display_df.columns if "▸ Status" in c]),
                use_container_width=True,
                height=520,
            )

            st.caption(f"Comparing **{fname_a}** (Source) vs **{fname_b}** (Output) — Sheet: **{sheet_name}**")
