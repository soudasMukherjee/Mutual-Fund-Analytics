from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import load_dim_fund, load_daily_returns_long
from utils.portfolio_optimizer import (
    build_returns_matrix, calibrate_markowitz_inputs, portfolio_performance,
    random_portfolios, max_sharpe_portfolio, min_volatility_portfolio, efficient_frontier,
)
from utils.theme import (
    register_plotly_template, inject_global_css, render_sidebar_brand, page_title,
    PRIMARY, SECONDARY, ACCENT, POSITIVE, NEGATIVE, CATEGORICAL_SEQUENCE, TEXT_DARK,
)

st.set_page_config(page_title="Efficient Frontier — Bluestock MF", page_icon="📐", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("📐", "Page 7 — Markowitz Efficient Frontier")

st.caption(
    "Modern Portfolio Theory: for a basket of funds, this finds the mix of weights that "
    "gives the **best possible return for each level of risk** — the Efficient Frontier — "
    "plus the Minimum-Volatility and Maximum-Sharpe (best risk-adjusted) portfolios. "
    "Long-only, fully-invested weights (no shorting, no leverage), consistent with how a "
    "retail investor would actually combine these funds."
)

fund_master = load_dim_fund()
nav_long = load_daily_returns_long()

available_schemes = sorted(fund_master["scheme_name"].unique())

# ---------------------------------------------------------------------------
# Controls
# ---------------------------------------------------------------------------
st.sidebar.markdown("### 🎚️ Portfolio Settings")

default_picks = available_schemes[:5]
selected = st.sidebar.multiselect(
    "Select funds (3–10)", options=available_schemes, default=default_picks,
)
risk_free_rate = st.sidebar.slider(
    "Risk-free rate (annual, %)", min_value=0.0, max_value=10.0, value=6.5, step=0.1,
) / 100.0
n_random = st.sidebar.select_slider(
    "Random portfolios (feasible region)", options=[500, 1000, 2000, 5000], value=2000,
)
n_frontier_points = st.sidebar.slider("Frontier resolution (points)", 10, 60, 30)

if len(selected) < 3:
    st.warning("Pick at least **3 funds** in the sidebar to build a frontier (5 recommended).")
    st.stop()
if len(selected) > 10:
    st.warning("Please select **10 or fewer** funds — keeps the optimiser fast and the chart readable.")
    st.stop()

# ---------------------------------------------------------------------------
# Calibrate
# ---------------------------------------------------------------------------
returns_wide = build_returns_matrix(nav_long, selected)

if returns_wide.shape[0] < 60:
    st.error(
        f"Only {returns_wide.shape[0]} overlapping trading days across the selected funds — "
        "need at least 60. Try a different combination with more shared history."
    )
    st.stop()

inputs = calibrate_markowitz_inputs(returns_wide)
mean_returns = inputs.mean_returns_annual
cov_matrix = inputs.cov_matrix_annual

with st.spinner("Solving for the efficient frontier..."):
    cloud = random_portfolios(n_random, mean_returns, cov_matrix, risk_free_rate)
    frontier = efficient_frontier(mean_returns, cov_matrix, n_points=n_frontier_points, risk_free_rate=risk_free_rate)
    max_sharpe = max_sharpe_portfolio(mean_returns, cov_matrix, risk_free_rate)
    min_vol = min_volatility_portfolio(mean_returns, cov_matrix, risk_free_rate)

st.markdown(f"### Basket: {', '.join(selected)}")
st.caption(
    f"Calibrated on **{inputs.n_obs:,}** overlapping trading days · "
    f"annualised expected returns & covariance from daily NAV history."
)

c1, c2, c3, c4 = st.columns(4)
c1.metric("🏆 Max-Sharpe return", f"{max_sharpe['return']*100:+.2f}%")
c2.metric("🏆 Max-Sharpe volatility", f"{max_sharpe['volatility']*100:.2f}%")
c3.metric("🏆 Max-Sharpe ratio", f"{max_sharpe['sharpe']:.2f}")
c4.metric("🛡️ Min-Vol volatility", f"{min_vol['volatility']*100:.2f}%")

st.divider()

# ---------------------------------------------------------------------------
# Efficient frontier chart
# ---------------------------------------------------------------------------
st.markdown("### 📈 Risk vs Return — Efficient Frontier")

fig = go.Figure()

# Random-portfolio cloud, colored by Sharpe ratio
fig.add_trace(go.Scatter(
    x=cloud["volatility"] * 100, y=cloud["return"] * 100, mode="markers",
    marker=dict(
        size=5, color=cloud["sharpe"], colorscale="Blues", showscale=True,
        colorbar=dict(title="Sharpe"), opacity=0.55,
    ),
    name="Random portfolios",
    hovertemplate="Vol: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>",
))

# Efficient frontier line
fig.add_trace(go.Scatter(
    x=frontier["volatility"] * 100, y=frontier["return"] * 100, mode="lines",
    line=dict(color=PRIMARY, width=4), name="Efficient frontier",
    hovertemplate="Vol: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>",
))

# Individual funds
fund_vols = np.sqrt(np.diag(cov_matrix.values)) * 100
fund_rets = mean_returns.values * 100
fig.add_trace(go.Scatter(
    x=fund_vols, y=fund_rets, mode="markers+text",
    marker=dict(size=12, color=CATEGORICAL_SEQUENCE[3], symbol="diamond", line=dict(width=1, color="white")),
    text=[s.split(" - ")[0][:18] for s in selected], textposition="top center",
    name="Individual funds",
    hovertemplate="%{text}<br>Vol: %{x:.2f}%<br>Return: %{y:.2f}%<extra></extra>",
))

# Max Sharpe + Min Vol stars
fig.add_trace(go.Scatter(
    x=[max_sharpe["volatility"] * 100], y=[max_sharpe["return"] * 100], mode="markers",
    marker=dict(size=20, color=ACCENT, symbol="star", line=dict(width=1.5, color=TEXT_DARK)),
    name="Max Sharpe portfolio",
    hovertemplate=f"Max Sharpe<br>Vol: {max_sharpe['volatility']*100:.2f}%<br>"
                   f"Return: {max_sharpe['return']*100:.2f}%<br>Sharpe: {max_sharpe['sharpe']:.2f}<extra></extra>",
))
fig.add_trace(go.Scatter(
    x=[min_vol["volatility"] * 100], y=[min_vol["return"] * 100], mode="markers",
    marker=dict(size=18, color=POSITIVE, symbol="star", line=dict(width=1.5, color="white")),
    name="Min Volatility portfolio",
    hovertemplate=f"Min Vol<br>Vol: {min_vol['volatility']*100:.2f}%<br>"
                   f"Return: {min_vol['return']*100:.2f}%<extra></extra>",
))

fig.update_layout(
    height=580, hovermode="closest",
    xaxis_title="Annualised Volatility (Risk) %", yaxis_title="Annualised Expected Return %",
    legend=dict(orientation="h", y=-0.15),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Weight tables
# ---------------------------------------------------------------------------
st.markdown("### ⚖️ Optimal Portfolio Weights")

wcol1, wcol2 = st.columns(2)
with wcol1:
    st.markdown("**🏆 Maximum Sharpe Ratio Portfolio**")
    ws_df = pd.DataFrame({
        "Fund": selected, "Weight %": (max_sharpe["weights"] * 100).round(2),
    }).sort_values("Weight %", ascending=False)
    st.dataframe(ws_df, use_container_width=True, hide_index=True)

with wcol2:
    st.markdown("**🛡️ Minimum Volatility Portfolio**")
    wv_df = pd.DataFrame({
        "Fund": selected, "Weight %": (min_vol["weights"] * 100).round(2),
    }).sort_values("Weight %", ascending=False)
    st.dataframe(wv_df, use_container_width=True, hide_index=True)

with st.expander("📋 Correlation matrix (selected funds)"):
    st.dataframe(
        inputs.corr_matrix.round(2).style.background_gradient(cmap="RdBu_r", vmin=-1, vmax=1),
        use_container_width=True,
    )

with st.expander("📋 Methodology & caveats"):
    st.markdown(
        f"""
        - **Model**: classical Markowitz mean-variance optimisation. Expected returns and the
          covariance matrix are estimated from each fund's own historical daily returns
          (annualised: mean × 252, covariance × 252) — no forward-looking assumptions.
        - **Constraints**: long-only (0 ≤ weight ≤ 1 per fund), fully invested (weights sum to 100%).
          No shorting or leverage — matches how a retail investor actually allocates across funds.
        - **Solver**: `scipy.optimize.minimize` (SLSQP) — minimises volatility for Min-Vol, minimises
          negative Sharpe for Max-Sharpe, and re-solves min-vol at {n_frontier_points} target-return
          levels to trace the frontier curve itself.
        - **Risk-free rate** used for Sharpe: **{risk_free_rate*100:.1f}%** annual (adjustable in the sidebar).
        - **Caveat**: like all mean-variance optimisation, this is only as good as the historical
          window it's calibrated on — it assumes the future correlation and volatility structure
          resembles the past, and is sensitive to the specific funds/period chosen.
        """
    )
