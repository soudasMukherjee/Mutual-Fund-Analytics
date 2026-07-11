from __future__ import annotations

import sys
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import (
    load_dim_fund, load_fact_nav, load_fact_performance,
    load_benchmark_indices, BENCHMARK_NAME_TO_INDEX,
)
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title,
    PRIMARY, SECONDARY,
)

st.set_page_config(page_title="NAV Detail — Bluestock MF", page_icon="🔍", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("🔍", "NAV Detail (Drill-Through)")

fund_master = load_dim_fund()
perf = load_fact_performance()
nav_df = load_fact_nav()

# ---------------------------------------------------------------------------
# Resolve which fund to show: drill-through from Page 2, or manual pick here
# ---------------------------------------------------------------------------
default_code = st.session_state.get("drillthrough_amfi_code")

code_to_name = dict(zip(fund_master["amfi_code"], fund_master["scheme_name"]))
options = sorted(fund_master["scheme_name"].unique())

if default_code and default_code in code_to_name:
    default_name = code_to_name[default_code]
    st.info(f"📌 Drilled through from the Page 2 scorecard: **{default_name}**")
else:
    default_name = options[0]

chosen_name = st.selectbox("Fund", options=options, index=options.index(default_name))
fund_row = fund_master[fund_master["scheme_name"] == chosen_name].iloc[0]
amfi_code = int(fund_row["amfi_code"])
perf_row = perf[perf["amfi_code"] == amfi_code]

st.markdown(f"## {chosen_name}")
st.caption(f"{fund_row['fund_house']} · {fund_row['category']} · {fund_row['plan']} · AMFI {amfi_code}")

# ---------------------------------------------------------------------------
# KPI row for the selected fund
# ---------------------------------------------------------------------------
if not perf_row.empty:
    p = perf_row.iloc[0]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("3-Yr Return", f"{p['return_3yr_pct']:.2f}%")
    c2.metric("Sharpe Ratio", f"{p['sharpe_ratio']:.2f}")
    c3.metric("Std Dev (ann.)", f"{p['std_dev_ann_pct']:.2f}%")
    c4.metric("Max Drawdown", f"{p['max_drawdown_pct']:.2f}%")
    c5.metric("Expense Ratio", f"{p['expense_ratio_pct']:.2f}%")

st.divider()

# ---------------------------------------------------------------------------
# NAV history + benchmark overlay
# ---------------------------------------------------------------------------
fund_nav = nav_df[nav_df["amfi_code"] == amfi_code].sort_values("date")

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=fund_nav["date"], y=fund_nav["nav"], mode="lines",
    name="NAV", line=dict(color=PRIMARY, width=2.5),
    hovertemplate="%{x|%d %b %Y}<br>NAV: ₹%{y:.2f}<extra></extra>",
))

index_key = BENCHMARK_NAME_TO_INDEX.get(fund_row["benchmark"])
if index_key:
    bm_df = load_benchmark_indices()
    bm_series = bm_df[bm_df["index_name"] == index_key].sort_values("date")
    if not fund_nav.empty:
        bm_series = bm_series[bm_series["date"] >= fund_nav["date"].min()]
    if not bm_series.empty and not fund_nav.empty:
        # Rescale benchmark onto the fund's NAV starting level for visual comparability
        scale = fund_nav["nav"].iloc[0] / bm_series["close_value"].iloc[0]
        fig.add_trace(go.Scatter(
            x=bm_series["date"], y=bm_series["close_value"] * scale, mode="lines",
            name=f"Benchmark ({fund_row['benchmark']}, rescaled)",
            line=dict(color=SECONDARY, width=2, dash="dash"),
            hovertemplate="%{x|%d %b %Y}<br>Benchmark (rescaled): ₹%{y:.2f}<extra></extra>",
        ))

fig.update_layout(height=480, hovermode="x unified", yaxis_title="NAV (₹)", xaxis_title=None)
st.plotly_chart(fig, use_container_width=True)

with st.expander("📋 Raw NAV history"):
    st.dataframe(fund_nav[["date", "nav", "daily_return_pct"]], use_container_width=True, hide_index=True)

if st.button("⬅ Back to Fund Performance"):
    st.switch_page("pages/2_Fund_Performance.py")
