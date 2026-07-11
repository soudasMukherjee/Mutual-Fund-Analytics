"""
Bluestock Mutual Fund Analytics — Streamlit Dashboard
=======================================================
A Streamlit alternative to the Power BI dashboard brief. Run with:

    streamlit run app.py

Pages (left sidebar):
  1. Industry Overview
  2. Fund Performance
  3. Investor Analytics
  4. SIP & Market Trends
  5. NAV Detail (drill-through target from the Page 2 fund table)
"""

from __future__ import annotations

import streamlit as st

from utils.data_loader import verify_data_connection, EXPECTED_TABLES
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title,
)

st.set_page_config(
    page_title="Bluestock MF Analytics",
    page_icon="🔷",
    layout="wide",
    initial_sidebar_state="expanded",
)

register_plotly_template()
inject_global_css()
render_sidebar_brand()

page_title("🔷", "Bluestock Mutual Fund Analytics")
st.caption(
    "Streamlit dashboard — a Power BI alternative built on the same cleaned data pipeline "
    "(cleaned CSVs + the Day-2 SQLite star schema)."
)

# ---------------------------------------------------------------------------
# Task 1 — "Connect to data ... verify all 8 tables load ... relationships"
# ---------------------------------------------------------------------------
st.markdown("## 🔌 Data Connection Status")

status = verify_data_connection()

col1, col2 = st.columns([1, 2])
with col1:
    if status["source"] == "sqlite":
        st.success(f"Connected via **SQLite** to:\n\n`{status['db_path']}`")
    else:
        st.warning(
            "`bluestock_mf.db` not found — falling back to the cleaned CSVs in "
            "`Data/processed/`. All pages still work; you're just not pointed at the "
            "warehouse. (This mirrors how Power BI would fail over if the ODBC "
            "connection couldn't reach the file.)"
        )

    n_ok = sum(1 for t in status["tables"].values() if t["loaded"])
    if status["all_ok"]:
        st.success(f"✅ All {n_ok}/{len(EXPECTED_TABLES)} tables loaded successfully.")
    else:
        st.error(f"⚠️ Only {n_ok}/{len(EXPECTED_TABLES)} tables loaded — see details.")

with col2:
    st.markdown("**Table load status**")
    rows = []
    for t in EXPECTED_TABLES:
        info = status["tables"][t]
        rows.append({
            "Table": t,
            "Loaded": "✅" if info["loaded"] else "❌",
            "Rows": f"{info['rows']:,}" if info["loaded"] else "—",
            "Error": info["error"] or "",
        })
    st.dataframe(rows, use_container_width=True, hide_index=True)

with st.expander("🔗 Relationships (join keys)"):
    st.markdown(
        "The warehouse is a star schema: `dim_fund` and `dim_date` are dimensions; "
        "everything else is a fact table keyed back to them."
    )
    for left, right in status["relationships"]:
        st.markdown(f"- `{left}` ↔ `{right}`")

st.divider()

st.markdown(
    """
    ### 👈 Use the sidebar to navigate

    | Page | Covers |
    |---|---|
    | **1 · Industry Overview** | KPI cards, AUM trend 2022–2025, AUM by AMC |
    | **2 · Fund Performance** | Return vs risk scatter, sortable scorecard, NAV vs benchmark, drill-through |
    | **3 · Investor Analytics** | Transactions by state, SIP/Lumpsum/Redemption split, age-group SIP, monthly volume |
    | **4 · SIP & Market Trends** | SIP inflow vs Nifty 50, category-inflow heatmap, top-5 categories FY25 |

    Every chart has native hover tooltips (Plotly), and every page has its own slicers
    in the sidebar. Use **Export Report** (see `export_report.py`) to generate the PDF
    and per-page PNGs for offline sharing.
    """
)
