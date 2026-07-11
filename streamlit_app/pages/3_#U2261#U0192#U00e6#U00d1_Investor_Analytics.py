from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import load_fact_transactions
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title,
    PRIMARY, SECONDARY, CATEGORICAL_SEQUENCE,
)

st.set_page_config(page_title="Investor Analytics — Bluestock MF", page_icon="👥", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("👥", "Page 3 — Investor Analytics")

tx = load_fact_transactions()

# ---------------------------------------------------------------------------
# Slicers — state, age group, city tier
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 🎚️ Slicers")
states = st.sidebar.multiselect("State", sorted(tx["state"].dropna().unique()))
age_groups = st.sidebar.multiselect("Age Group", sorted(tx["age_group"].dropna().unique()))
city_tiers = st.sidebar.multiselect("City Tier", sorted(tx["city_tier"].dropna().unique()))

filtered = tx.copy()
if states:
    filtered = filtered[filtered["state"].isin(states)]
if age_groups:
    filtered = filtered[filtered["age_group"].isin(age_groups)]
if city_tiers:
    filtered = filtered[filtered["city_tier"].isin(city_tiers)]

st.caption(f"Showing **{len(filtered):,}** of {len(tx):,} transactions after slicers.")

row1_left, row1_right = st.columns([3, 2])

# ---------------------------------------------------------------------------
# Bar: transaction amount by state
# ---------------------------------------------------------------------------
with row1_left:
    st.markdown("### 🗺️ Transaction Amount by State")
    by_state = (
        filtered.groupby("state", as_index=False)["amount_inr"].sum()
        .sort_values("amount_inr", ascending=True)
    )
    by_state["amount_cr"] = by_state["amount_inr"] / 1e7
    fig_state = px.bar(
        by_state, x="amount_cr", y="state", orientation="h",
        color="amount_cr", color_continuous_scale=[SECONDARY, PRIMARY],
        labels={"amount_cr": "Transaction Amount (₹ Cr)", "state": ""},
    )
    fig_state.update_layout(height=440, coloraxis_showscale=False)
    fig_state.update_traces(hovertemplate="<b>%{y}</b><br>₹%{x:.1f} Cr<extra></extra>")
    st.plotly_chart(fig_state, use_container_width=True)

# ---------------------------------------------------------------------------
# Donut: SIP / Lumpsum / Redemption split
# ---------------------------------------------------------------------------
with row1_right:
    st.markdown("### 🍩 Transaction Type Split")
    by_type = filtered.groupby("transaction_type", as_index=False)["amount_inr"].sum()
    fig_donut = px.pie(
        by_type, names="transaction_type", values="amount_inr", hole=0.55,
        color_discrete_sequence=CATEGORICAL_SEQUENCE,
    )
    fig_donut.update_traces(
        textinfo="percent+label",
        hovertemplate="<b>%{label}</b><br>₹%{value:,.0f}<br>%{percent}<extra></extra>",
    )
    fig_donut.update_layout(height=440, showlegend=False)
    st.plotly_chart(fig_donut, use_container_width=True)

st.divider()

row2_left, row2_right = st.columns([2, 3])

# ---------------------------------------------------------------------------
# Bar: age group vs avg SIP amount
# ---------------------------------------------------------------------------
with row2_left:
    st.markdown("### 👤 Avg SIP Amount by Age Group")
    sip_only = filtered[filtered["transaction_type"] == "SIP"]
    by_age = sip_only.groupby("age_group", as_index=False)["amount_inr"].mean()
    age_order = ["18-25", "26-35", "36-45", "46-55", "56+"]
    by_age["age_group"] = pd.Categorical(by_age["age_group"], categories=age_order, ordered=True)
    by_age = by_age.sort_values("age_group")
    fig_age = px.bar(
        by_age, x="age_group", y="amount_inr",
        color="age_group", color_discrete_sequence=CATEGORICAL_SEQUENCE,
        labels={"amount_inr": "Avg SIP Amount (₹)", "age_group": "Age Group"},
    )
    fig_age.update_layout(height=420, showlegend=False)
    fig_age.update_traces(hovertemplate="<b>%{x}</b><br>Avg SIP: ₹%{y:,.0f}<extra></extra>")
    st.plotly_chart(fig_age, use_container_width=True)

# ---------------------------------------------------------------------------
# Line: monthly transaction volume
# ---------------------------------------------------------------------------
with row2_right:
    st.markdown("### 📅 Monthly Transaction Volume")
    monthly = filtered.copy()
    monthly["year_month"] = monthly["transaction_date"].dt.to_period("M").astype(str)
    vol = monthly.groupby("year_month", as_index=False).agg(
        tx_count=("investor_id", "count"), amount=("amount_inr", "sum")
    )
    fig_vol = px.line(
        vol, x="year_month", y="tx_count", markers=True,
        labels={"year_month": "Month", "tx_count": "Number of Transactions"},
    )
    fig_vol.update_traces(line=dict(color=PRIMARY, width=3), marker=dict(size=7),
                           hovertemplate="%{x}<br>Transactions: %{y:,}<extra></extra>")
    fig_vol.update_layout(height=420)
    st.plotly_chart(fig_vol, use_container_width=True)

with st.expander("📋 Underlying transaction summary"):
    st.dataframe(
        filtered.groupby(["state", "transaction_type"], as_index=False)["amount_inr"].sum()
        .sort_values("amount_inr", ascending=False),
        use_container_width=True, hide_index=True,
    )
