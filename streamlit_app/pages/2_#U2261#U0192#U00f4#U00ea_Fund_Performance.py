from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import (
    load_fact_performance, load_fund_scorecard, load_fact_nav,
    load_benchmark_indices, load_dim_fund, BENCHMARK_NAME_TO_INDEX,
)
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title,
    PRIMARY, SECONDARY, POSITIVE, NEGATIVE,
)

st.set_page_config(page_title="Fund Performance — Bluestock MF", page_icon="📈", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("📈", "Page 2 — Fund Performance")

perf = load_fact_performance()
scorecard = load_fund_scorecard()
fund_master = load_dim_fund()

# ---------------------------------------------------------------------------
# Slicers (sidebar) — fund house, category, plan
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 🎚️ Slicers")
fund_houses = st.sidebar.multiselect("Fund House", sorted(perf["fund_house"].dropna().unique()))
categories = st.sidebar.multiselect("Category", sorted(perf["category"].dropna().unique()))
plans = st.sidebar.multiselect("Plan", sorted(perf["plan"].dropna().unique()))

filtered = perf.copy()
if fund_houses:
    filtered = filtered[filtered["fund_house"].isin(fund_houses)]
if categories:
    filtered = filtered[filtered["category"].isin(categories)]
if plans:
    filtered = filtered[filtered["plan"].isin(plans)]

st.caption(f"Showing **{len(filtered)}** of {len(perf)} schemes after slicers.")

# ---------------------------------------------------------------------------
# Scatter: return (X) vs risk/StdDev (Y), bubble size = AUM
# ---------------------------------------------------------------------------
st.markdown("### 🎯 Return vs Risk (bubble size = AUM)")

scatter_df = filtered.dropna(subset=["return_3yr_pct", "std_dev_ann_pct", "aum_crore"]).copy()
fig_scatter = px.scatter(
    scatter_df,
    x="return_3yr_pct", y="std_dev_ann_pct",
    size="aum_crore", color="category",
    hover_name="scheme_name",
    hover_data={"fund_house": True, "sharpe_ratio": ":.2f", "aum_crore": ":,.0f",
                "return_3yr_pct": ":.2f", "std_dev_ann_pct": ":.2f"},
    size_max=45,
    labels={"return_3yr_pct": "3-Yr Return (%)", "std_dev_ann_pct": "Risk / Std Dev (annualised, %)"},
    color_discrete_sequence=px.colors.qualitative.Bold,
)
fig_scatter.update_layout(height=520, legend=dict(orientation="h", y=-0.2))
st.plotly_chart(fig_scatter, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Sortable fund scorecard table + drill-through
# ---------------------------------------------------------------------------
st.markdown("### 🏆 Fund Scorecard (sortable — click a row's AMFI code below to view NAV detail)")

sc_cols = ["amfi_code", "scheme_name", "return_3yr_pct", "sharpe_ratio", "alpha",
           "expense_ratio_pct", "max_drawdown_pct", "fund_score_0_100"]
sc_view = scorecard[sc_cols].sort_values("fund_score_0_100", ascending=False)

st.dataframe(
    sc_view,
    use_container_width=True,
    hide_index=True,
    column_config={
        "fund_score_0_100": st.column_config.ProgressColumn(
            "Fund Score (0–100)", min_value=0, max_value=100, format="%.0f"
        ),
        "return_3yr_pct": st.column_config.NumberColumn("3-Yr Return (%)", format="%.2f"),
        "sharpe_ratio": st.column_config.NumberColumn("Sharpe", format="%.2f"),
        "alpha": st.column_config.NumberColumn("Alpha", format="%.2f"),
        "expense_ratio_pct": st.column_config.NumberColumn("Expense (%)", format="%.2f"),
        "max_drawdown_pct": st.column_config.NumberColumn("Max Drawdown (%)", format="%.2f"),
    },
)

st.markdown("**🔍 Drill-through to NAV Detail**")
drill_col1, drill_col2 = st.columns([2, 1])
with drill_col1:
    scheme_options = dict(zip(scorecard["scheme_name"], scorecard["amfi_code"]))
    chosen_name = st.selectbox("Pick a fund from the scorecard", options=list(scheme_options.keys()))
with drill_col2:
    st.write("")
    st.write("")
    if st.button("Open NAV Detail →", type="primary", use_container_width=True):
        st.session_state["drillthrough_amfi_code"] = scheme_options[chosen_name]
        st.switch_page("pages/5_NAV_Detail.py")

st.divider()

# ---------------------------------------------------------------------------
# NAV line vs benchmark
# ---------------------------------------------------------------------------
st.markdown("### 📉 NAV vs Benchmark")

nav_fund_choice = st.selectbox(
    "Select a fund", options=sorted(fund_master["scheme_name"].unique()), key="nav_vs_bm_fund",
)
fund_row = fund_master[fund_master["scheme_name"] == nav_fund_choice].iloc[0]
amfi_code = int(fund_row["amfi_code"])
benchmark_name = fund_row["benchmark"]
index_key = BENCHMARK_NAME_TO_INDEX.get(benchmark_name)

nav_df = load_fact_nav()
fund_nav = nav_df[nav_df["amfi_code"] == amfi_code].sort_values("date")

fig_nav = go.Figure()
if not fund_nav.empty:
    base_nav = fund_nav["nav"].iloc[0]
    fig_nav.add_trace(go.Scatter(
        x=fund_nav["date"], y=fund_nav["nav"] / base_nav * 100,
        mode="lines", name=nav_fund_choice, line=dict(color=PRIMARY, width=2.5),
        hovertemplate="%{x|%d %b %Y}<br>Indexed NAV: %{y:.1f}<extra></extra>",
    ))

if index_key:
    bm_df = load_benchmark_indices()
    bm_series = bm_df[bm_df["index_name"] == index_key].sort_values("date")
    bm_series = bm_series[bm_series["date"] >= fund_nav["date"].min()] if not fund_nav.empty else bm_series
    if not bm_series.empty:
        base_bm = bm_series["close_value"].iloc[0]
        fig_nav.add_trace(go.Scatter(
            x=bm_series["date"], y=bm_series["close_value"] / base_bm * 100,
            mode="lines", name=f"Benchmark ({benchmark_name})",
            line=dict(color=SECONDARY, width=2, dash="dash"),
            hovertemplate="%{x|%d %b %Y}<br>Indexed Benchmark: %{y:.1f}<extra></extra>",
        ))
else:
    st.info(
        f"No matching index series found in `benchmark_indices_clean.csv` for this fund's "
        f"benchmark (**{benchmark_name}**) — showing NAV only."
    )

fig_nav.update_layout(
    height=460, hovermode="x unified",
    yaxis_title="Indexed to 100 at start of period",
    xaxis_title=None,
)
st.plotly_chart(fig_nav, use_container_width=True)
