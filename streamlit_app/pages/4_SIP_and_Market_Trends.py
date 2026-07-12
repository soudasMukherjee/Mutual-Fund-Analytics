from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import (
    load_fact_sip_industry, load_benchmark_indices, load_category_inflows,
)
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title,
    PRIMARY, SECONDARY, ACCENT, NEGATIVE,
)

st.set_page_config(page_title="SIP & Market Trends — Bluestock MF", page_icon="💰", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("💰", "Page 4 — SIP & Market Trends")

sip = load_fact_sip_industry().sort_values("year_month")
bm = load_benchmark_indices()
cat = load_category_inflows()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 🎚️ Filters")

all_categories = sorted(cat["category"].unique())
selected_categories = st.sidebar.multiselect("Fund categories", options=all_categories, default=all_categories)
top_n = st.sidebar.slider("Top N categories (net inflow)", min_value=3, max_value=max(3, len(all_categories)), value=5)

months_sorted = sorted(sip["year_month"].unique())
month_start, month_end = st.sidebar.select_slider(
    "SIP / Nifty trend range", options=months_sorted, value=(months_sorted[0], months_sorted[-1]),
)

cat_filtered = cat[cat["category"].isin(selected_categories)] if selected_categories else cat.iloc[0:0]

# ---------------------------------------------------------------------------
# Dual-axis: SIP inflow (bar) + Nifty 50 (line), 2022-2025
# ---------------------------------------------------------------------------
st.markdown("### 📊 SIP Inflow vs Nifty 50 (2022–2025)")

nifty = bm[bm["index_name"] == "NIFTY50"].copy()
nifty["year_month"] = nifty["date"].dt.to_period("M").astype(str)
nifty_monthly = nifty.groupby("year_month", as_index=False)["close_value"].last()

merged = sip.merge(nifty_monthly, on="year_month", how="left").sort_values("year_month")
merged = merged[(merged["year_month"] >= month_start) & (merged["year_month"] <= month_end)]

fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
fig_dual.add_trace(
    go.Bar(x=merged["year_month"], y=merged["sip_inflow_crore"], name="SIP Inflow (₹ Cr)",
           marker_color=SECONDARY,
           hovertemplate="%{x}<br>SIP Inflow: ₹%{y:,.0f} Cr<extra></extra>"),
    secondary_y=False,
)
fig_dual.add_trace(
    go.Scatter(x=merged["year_month"], y=merged["close_value"], name="Nifty 50 (month-end close)",
               mode="lines+markers", line=dict(color=PRIMARY, width=3), marker=dict(size=6),
               hovertemplate="%{x}<br>Nifty 50: %{y:,.0f}<extra></extra>"),
    secondary_y=True,
)
fig_dual.update_layout(
    height=460, hovermode="x unified",
    legend=dict(orientation="h", y=1.12),
    xaxis=dict(tickangle=-45),
)
fig_dual.update_yaxes(title_text="SIP Inflow (₹ Cr)", secondary_y=False)
fig_dual.update_yaxes(title_text="Nifty 50 Index", secondary_y=True, showgrid=False)
st.plotly_chart(fig_dual, use_container_width=True)

st.divider()

left, right = st.columns([3, 2])

# ---------------------------------------------------------------------------
# Heatmap: category inflow by month
# ---------------------------------------------------------------------------
with left:
    st.markdown("### 🔥 Category Inflow Heatmap (FY25)")
    pivot = cat_filtered.pivot_table(index="category", columns="month", values="net_inflow_crore", aggfunc="sum")
    pivot = pivot.reindex(sorted(pivot.columns), axis=1)
    fig_heat = px.imshow(
        pivot, color_continuous_scale=[NEGATIVE, "#FFFFFF", PRIMARY],
        aspect="auto", labels=dict(x="Month", y="Category", color="Net Inflow (₹ Cr)"),
        color_continuous_midpoint=0,
    )
    fig_heat.update_traces(hovertemplate="%{y}<br>%{x}<br>₹%{z:,.0f} Cr<extra></extra>")
    fig_heat.update_layout(height=460)
    st.plotly_chart(fig_heat, use_container_width=True)

# ---------------------------------------------------------------------------
# Top 5 categories by net inflow FY25
# ---------------------------------------------------------------------------
with right:
    st.markdown(f"### 🏅 Top {top_n} Categories by Net Inflow (FY25)")
    top5 = (
        cat_filtered.groupby("category", as_index=False)["net_inflow_crore"].sum()
        .sort_values("net_inflow_crore", ascending=False)
        .head(top_n)
    )
    fig_top5 = px.bar(
        top5.sort_values("net_inflow_crore"), x="net_inflow_crore", y="category", orientation="h",
        color="net_inflow_crore", color_continuous_scale=[SECONDARY, ACCENT],
        labels={"net_inflow_crore": "Net Inflow FY25 (₹ Cr)", "category": ""},
    )
    fig_top5.update_layout(height=460, coloraxis_showscale=False)
    fig_top5.update_traces(hovertemplate="<b>%{y}</b><br>₹%{x:,.0f} Cr<extra></extra>")
    st.plotly_chart(fig_top5, use_container_width=True)

with st.expander("📋 Full FY25 category inflow table"):
    st.dataframe(
        cat_filtered.groupby("category", as_index=False)["net_inflow_crore"].sum()
        .sort_values("net_inflow_crore", ascending=False),
        use_container_width=True, hide_index=True,
    )
