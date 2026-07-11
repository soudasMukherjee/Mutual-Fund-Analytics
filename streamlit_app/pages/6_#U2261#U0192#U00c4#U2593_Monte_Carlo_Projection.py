from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import load_dim_fund, load_fact_nav
from utils.monte_carlo import calibrate_gbm, simulate_gbm_paths, summarize_paths, risk_summary
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title,
    PRIMARY, SECONDARY, ACCENT, POSITIVE, NEGATIVE,
)

st.set_page_config(page_title="Monte Carlo Projection — Bluestock MF", page_icon="🎲", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("🎲", "Page 6 — Monte Carlo NAV Projection")

st.caption(
    "Simulates thousands of possible future NAV paths using Geometric Brownian Motion, "
    "calibrated on each fund's own historical daily returns (mean + volatility). This shows "
    "a **range of plausible outcomes consistent with the fund's own track record** — it is "
    "not a forecast or a guarantee, and assumes future volatility resembles the past."
)

fund_master = load_dim_fund()
nav_df = load_fact_nav()

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 🎚️ Simulation Settings")
scheme_choice = st.sidebar.selectbox("Fund", options=sorted(fund_master["scheme_name"].unique()))
years = st.sidebar.slider("Projection horizon (years)", min_value=1, max_value=10, value=5)
n_sims = st.sidebar.select_slider(
    "Number of simulated paths", options=[500, 1000, 2000, 5000, 10000], value=2000
)
show_sample_paths = st.sidebar.checkbox("Show sample individual paths", value=True)
seed = st.sidebar.number_input("Random seed (for reproducibility)", value=42, step=1)

fund_row = fund_master[fund_master["scheme_name"] == scheme_choice].iloc[0]
amfi_code = int(fund_row["amfi_code"])

fund_nav = nav_df[nav_df["amfi_code"] == amfi_code].sort_values("date").copy()
fund_nav["daily_return"] = fund_nav["nav"].pct_change()

if fund_nav.empty or fund_nav["daily_return"].dropna().shape[0] < 30:
    st.error("Not enough NAV history for this fund to calibrate a simulation (need 30+ daily observations).")
    st.stop()

# ---------------------------------------------------------------------------
# Calibrate + simulate
# ---------------------------------------------------------------------------
params = calibrate_gbm(fund_nav["daily_return"])
start_nav = float(fund_nav["nav"].iloc[-1])
start_date = fund_nav["date"].iloc[-1]

paths = simulate_gbm_paths(
    start_nav=start_nav, params=params, years=years, n_simulations=n_sims, seed=int(seed),
)
bands = summarize_paths(paths, start_date=start_date)
risk = risk_summary(paths, start_nav=start_nav)

# ---------------------------------------------------------------------------
# Calibration summary
# ---------------------------------------------------------------------------
st.markdown(f"### {scheme_choice}")
st.caption(f"{fund_row['fund_house']} · {fund_row['category']} · calibrated on {params.n_obs:,} daily returns")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Current NAV", f"₹{start_nav:,.2f}", f"as of {pd.Timestamp(start_date):%d %b %Y}")
c2.metric("Historical Annual Return", f"{params.mu_annual*100:+.2f}%")
c3.metric("Historical Annual Volatility", f"{params.sigma_annual*100:.2f}%")
c4.metric(f"Median NAV in {years}Y", f"₹{risk['median_final_nav']:,.2f}",
          f"{risk['median_total_return_pct']:+.1f}%")

st.divider()

# ---------------------------------------------------------------------------
# Fan chart — uncertainty bands
# ---------------------------------------------------------------------------
st.markdown("### 📈 Projected NAV — Uncertainty Bands")

fig = go.Figure()

# 5-95 band
fig.add_trace(go.Scatter(
    x=bands["date"], y=bands["p95"], mode="lines", line=dict(width=0), showlegend=False,
    hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=bands["date"], y=bands["p5"], mode="lines", line=dict(width=0),
    fill="tonexty", fillcolor="rgba(0,180,216,0.15)", name="5th–95th percentile",
    hovertemplate="%{x|%d %b %Y}<br>P5: ₹%{y:.2f}<extra></extra>",
))

# 25-75 band
fig.add_trace(go.Scatter(
    x=bands["date"], y=bands["p75"], mode="lines", line=dict(width=0), showlegend=False,
    hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=bands["date"], y=bands["p25"], mode="lines", line=dict(width=0),
    fill="tonexty", fillcolor="rgba(0,180,216,0.35)", name="25th–75th percentile",
    hovertemplate="%{x|%d %b %Y}<br>P25: ₹%{y:.2f}<extra></extra>",
))

# Median line
fig.add_trace(go.Scatter(
    x=bands["date"], y=bands["p50"], mode="lines", line=dict(color=PRIMARY, width=3),
    name="Median projection",
    hovertemplate="%{x|%d %b %Y}<br>Median: ₹%{y:.2f}<extra></extra>",
))

# Optional: a handful of individual sample paths for texture
if show_sample_paths:
    sample_idx = np.random.default_rng(0).choice(paths.shape[0], size=min(25, paths.shape[0]), replace=False)
    for i in sample_idx:
        fig.add_trace(go.Scatter(
            x=bands["date"], y=paths[i], mode="lines",
            line=dict(color="rgba(11,61,145,0.10)", width=1), showlegend=False, hoverinfo="skip",
        ))

# Historical NAV tail for context (last ~2 years)
hist_tail = fund_nav[fund_nav["date"] >= fund_nav["date"].max() - pd.Timedelta(days=730)]
fig.add_trace(go.Scatter(
    x=hist_tail["date"], y=hist_tail["nav"], mode="lines", line=dict(color=NEGATIVE, width=2),
    name="Historical NAV",
    hovertemplate="%{x|%d %b %Y}<br>Historical NAV: ₹%{y:.2f}<extra></extra>",
))

fig.add_vline(x=start_date, line_dash="dot", line_color=ACCENT, annotation_text="Simulation start")

fig.update_layout(
    height=560, hovermode="x unified",
    yaxis_title="NAV (₹)", xaxis_title=None,
    legend=dict(orientation="h", y=-0.15),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Risk/return summary panel
# ---------------------------------------------------------------------------
st.markdown(f"### 🎯 {years}-Year Outcome Summary ({n_sims:,} simulated paths)")

r1, r2, r3, r4 = st.columns(4)
with r1:
    st.markdown(
        f"""**Best case (95th pct.)**
        \n₹{risk['p95_final_nav']:,.2f}
        \n<span style="color:{POSITIVE};font-weight:700">{risk['best_case_return_pct']:+.1f}%</span>""",
        unsafe_allow_html=True,
    )
with r2:
    st.markdown(
        f"""**Median outcome**
        \n₹{risk['median_final_nav']:,.2f}
        \n<span style="color:{PRIMARY};font-weight:700">{risk['median_total_return_pct']:+.1f}%</span>""",
        unsafe_allow_html=True,
    )
with r3:
    st.markdown(
        f"""**Worst case (5th pct.)**
        \n₹{risk['p5_final_nav']:,.2f}
        \n<span style="color:{NEGATIVE};font-weight:700">{risk['worst_case_return_pct']:+.1f}%</span>""",
        unsafe_allow_html=True,
    )
with r4:
    loss_color = NEGATIVE if risk["prob_loss_pct"] > 30 else PRIMARY
    st.markdown(
        f"""**Probability of a loss**
        \n<span style="font-size:1.4rem;font-weight:700;color:{loss_color}">{risk['prob_loss_pct']:.1f}%</span>
        \nof simulated paths end below today's NAV""",
        unsafe_allow_html=True,
    )

with st.expander("📋 Methodology & caveats"):
    st.markdown(
        f"""
        - **Model**: Geometric Brownian Motion. Daily log-returns are drawn from
          `Normal(μ={params.mu_daily:.5f}, σ={params.sigma_daily:.5f})`, calibrated from this
          fund's own **{params.n_obs:,}** historical daily NAV changes, then compounded forward.
        - **Assumes**: returns are independently and identically distributed, volatility is
          constant, and the future statistically resembles the past. Real markets have fat tails,
          volatility clustering, and regime shifts that GBM does not capture — treat the bands as
          a *plausible range under historical-average conditions*, not a guarantee.
        - **Annualised drift**: {params.mu_annual*100:+.2f}% · **Annualised volatility**: {params.sigma_annual*100:.2f}%
        - Bands use business-day stepping (~{years * 252:,} trading days) starting from
          {pd.Timestamp(start_date):%d %b %Y}.
        - Re-running with a different random seed will shift individual sample paths slightly but
          the percentile bands are stable for n_simulations ≥ 1,000.
        """
    )

with st.expander("📋 Raw percentile-band data"):
    st.dataframe(
        bands[["date", "p5", "p25", "p50", "p75", "p95"]].iloc[::21],  # ~monthly rows to keep it readable
        use_container_width=True, hide_index=True,
    )
