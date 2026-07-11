from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import (
    load_fact_aum, load_fact_sip_industry, load_folio_counts, load_dim_fund,
)
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title, kpi_card,
    PRIMARY, SECONDARY,
)

st.set_page_config(page_title="Industry Overview — Bluestock MF", page_icon="📊", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("📊", "Page 1 — Industry Overview")

aum = load_fact_aum()
sip = load_fact_sip_industry()
folio = load_folio_counts()
funds = load_dim_fund()

latest_aum_date = aum["date"].max()
total_aum_latest = aum.loc[aum["date"] == latest_aum_date, "aum_crore"].sum()
total_schemes_latest = aum.loc[aum["date"] == latest_aum_date, "num_schemes"].sum()

sip_sorted = sip.sort_values("year_month")
latest_sip = sip_sorted.iloc[-1]

folio_sorted = folio.sort_values("month")
latest_folio = folio_sorted.iloc[-1]

# ---------------------------------------------------------------------------
# KPI cards
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        kpi_card("Total Industry AUM", f"₹{total_aum_latest/1e5:,.1f} L Cr", f"as of {latest_aum_date:%b %Y}"),
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        kpi_card("Monthly SIP Inflows", f"₹{latest_sip['sip_inflow_crore']:,.0f} Cr",
                  f"{latest_sip['year_month']} · YoY {latest_sip['yoy_growth_pct']:+.1f}%"),
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        kpi_card("Total Folios", f"{latest_folio['total_folios_crore']:.2f} Cr", f"as of {latest_folio['month']}"),
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        kpi_card("Schemes Tracked", f"{total_schemes_latest:,}", f"across {aum['fund_house'].nunique()} AMCs"),
        unsafe_allow_html=True,
    )

st.caption(
    "KPI figures are computed live from the cleaned dataset. Monthly SIP inflow and total-folio "
    "figures line up closely with the brief's reference numbers (₹31K Cr / 26.12 Cr); total AUM and "
    "scheme count reflect this dataset's actual coverage rather than the brief's placeholder figures."
)

st.divider()

# ---------------------------------------------------------------------------
# Line chart — industry AUM trend
# ---------------------------------------------------------------------------
left, right = st.columns([3, 2])

with left:
    st.markdown("### 📈 Industry AUM Trend (2022–2025)")
    aum_trend = aum.groupby("date", as_index=False)["aum_crore"].sum()
    aum_trend["aum_lakh_crore"] = aum_trend["aum_crore"] / 1e5

    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=aum_trend["date"], y=aum_trend["aum_lakh_crore"],
        mode="lines+markers", line=dict(color=PRIMARY, width=3),
        marker=dict(size=8),
        hovertemplate="%{x|%b %Y}<br>AUM: ₹%{y:.2f} L Cr<extra></extra>",
        name="Industry AUM",
    ))
    fig_trend.update_layout(
        yaxis_title="AUM (₹ Lakh Cr)", xaxis_title=None,
        height=420, hovermode="x unified",
    )
    st.plotly_chart(fig_trend, use_container_width=True)

with right:
    st.markdown("### 🏦 AUM by AMC (latest)")
    amc_latest = (
        aum[aum["date"] == latest_aum_date]
        .sort_values("aum_crore", ascending=True)
        .assign(aum_lakh_crore=lambda d: d["aum_crore"] / 1e5)
    )
    fig_amc = px.bar(
        amc_latest, x="aum_lakh_crore", y="fund_house", orientation="h",
        color="aum_lakh_crore", color_continuous_scale=[SECONDARY, PRIMARY],
        labels={"aum_lakh_crore": "AUM (₹ Lakh Cr)", "fund_house": ""},
        hover_data={"num_schemes": True},
    )
    fig_amc.update_layout(height=420, coloraxis_showscale=False)
    fig_amc.update_traces(
        hovertemplate="<b>%{y}</b><br>AUM: ₹%{x:.2f} L Cr<br>Schemes: %{customdata[0]}<extra></extra>"
    )
    st.plotly_chart(fig_amc, use_container_width=True)

st.divider()
with st.expander("📋 Underlying AUM-by-AMC data (latest snapshot)"):
    st.dataframe(
        amc_latest[["fund_house", "aum_crore", "num_schemes"]].sort_values("aum_crore", ascending=False),
        use_container_width=True, hide_index=True,
    )
