"""
Markowitz mean-variance portfolio optimisation (Efficient Frontier).

Given a basket of funds, this module:
  1. Builds a daily-return matrix from historical NAVs.
  2. Annualises expected return (mean) and the return covariance matrix.
  3. Solves, via ``scipy.optimize.minimize`` (SLSQP), for:
       - the Minimum-Volatility portfolio,
       - the Maximum-Sharpe-Ratio ("tangency") portfolio,
       - the Efficient Frontier itself (min-vol at each target return level).
  4. Generates random long-only portfolios for the background "cloud" that
     visually frames where the frontier sits relative to naive allocations.

Long-only, fully-invested portfolios are assumed throughout (weights in
[0, 1], sum to 1) — the standard classroom/industry convention and the
right default for a retail mutual-fund context (no shorting mutual funds).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

TRADING_DAYS_PER_YEAR = 252


# ---------------------------------------------------------------------------
# Data prep
# ---------------------------------------------------------------------------
def build_returns_matrix(nav_long: pd.DataFrame, scheme_names: list[str]) -> pd.DataFrame:
    """Pivot a long-format NAV/return frame (date, scheme_name, nav, daily_return)
    into a wide date x scheme daily-return matrix for the chosen funds, aligned
    on common trading dates (inner join across all selected funds).
    """
    subset = nav_long[nav_long["scheme_name"].isin(scheme_names)].copy()
    if "daily_return" not in subset.columns:
        subset = subset.sort_values(["scheme_name", "date"])
        subset["daily_return"] = subset.groupby("scheme_name")["nav"].pct_change()

    wide = subset.pivot_table(index="date", columns="scheme_name", values="daily_return")
    wide = wide[scheme_names]  # preserve selection order
    wide = wide.dropna(how="any")  # only dates where every fund has a return
    return wide


@dataclass
class MarkowitzInputs:
    scheme_names: list[str]
    mean_returns_annual: pd.Series      # annualised expected return per fund
    cov_matrix_annual: pd.DataFrame     # annualised covariance matrix
    n_obs: int
    corr_matrix: pd.DataFrame = field(default_factory=pd.DataFrame)


def calibrate_markowitz_inputs(returns_wide: pd.DataFrame) -> MarkowitzInputs:
    mean_daily = returns_wide.mean()
    cov_daily = returns_wide.cov()
    return MarkowitzInputs(
        scheme_names=list(returns_wide.columns),
        mean_returns_annual=mean_daily * TRADING_DAYS_PER_YEAR,
        cov_matrix_annual=cov_daily * TRADING_DAYS_PER_YEAR,
        n_obs=len(returns_wide),
        corr_matrix=returns_wide.corr(),
    )


# ---------------------------------------------------------------------------
# Portfolio math
# ---------------------------------------------------------------------------
def portfolio_performance(weights: np.ndarray, mean_returns: pd.Series, cov_matrix: pd.DataFrame,
                           risk_free_rate: float = 0.065) -> tuple[float, float, float]:
    ret = float(np.dot(weights, mean_returns.values))
    vol = float(np.sqrt(weights.T @ cov_matrix.values @ weights))
    sharpe = (ret - risk_free_rate) / vol if vol > 0 else 0.0
    return ret, vol, sharpe


def random_portfolios(n: int, mean_returns: pd.Series, cov_matrix: pd.DataFrame,
                       risk_free_rate: float = 0.065, seed: int = 42) -> pd.DataFrame:
    """Long-only random portfolios (Dirichlet-sampled weights) for the
    'feasible region' scatter cloud behind the efficient frontier.
    """
    rng = np.random.default_rng(seed)
    n_assets = len(mean_returns)
    weights_mat = rng.dirichlet(np.ones(n_assets), size=n)

    records = []
    for w in weights_mat:
        ret, vol, sharpe = portfolio_performance(w, mean_returns, cov_matrix, risk_free_rate)
        records.append({"return": ret, "volatility": vol, "sharpe": sharpe, "weights": w})
    return pd.DataFrame(records)


def _neg_sharpe(weights, mean_returns, cov_matrix, risk_free_rate):
    _, _, sharpe = portfolio_performance(weights, mean_returns, cov_matrix, risk_free_rate)
    return -sharpe


def _volatility(weights, mean_returns, cov_matrix):
    _, vol, _ = portfolio_performance(weights, mean_returns, cov_matrix)
    return vol


def _base_constraints(n_assets):
    bounds = tuple((0.0, 1.0) for _ in range(n_assets))
    x0 = np.repeat(1.0 / n_assets, n_assets)
    return bounds, x0


def max_sharpe_portfolio(mean_returns: pd.Series, cov_matrix: pd.DataFrame,
                          risk_free_rate: float = 0.065) -> dict:
    n = len(mean_returns)
    bounds, x0 = _base_constraints(n)
    constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
    result = minimize(
        _neg_sharpe, x0, args=(mean_returns, cov_matrix, risk_free_rate),
        method="SLSQP", bounds=bounds, constraints=constraints,
    )
    ret, vol, sharpe = portfolio_performance(result.x, mean_returns, cov_matrix, risk_free_rate)
    return {"weights": result.x, "return": ret, "volatility": vol, "sharpe": sharpe, "success": result.success}


def min_volatility_portfolio(mean_returns: pd.Series, cov_matrix: pd.DataFrame,
                              risk_free_rate: float = 0.065) -> dict:
    n = len(mean_returns)
    bounds, x0 = _base_constraints(n)
    constraints = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)
    result = minimize(
        _volatility, x0, args=(mean_returns, cov_matrix),
        method="SLSQP", bounds=bounds, constraints=constraints,
    )
    ret, vol, sharpe = portfolio_performance(result.x, mean_returns, cov_matrix, risk_free_rate)
    return {"weights": result.x, "return": ret, "volatility": vol, "sharpe": sharpe, "success": result.success}


def efficient_frontier(mean_returns: pd.Series, cov_matrix: pd.DataFrame,
                        n_points: int = 40, risk_free_rate: float = 0.065) -> pd.DataFrame:
    """Trace the frontier: for a range of target returns spanning the
    achievable range, find the minimum-volatility portfolio hitting that
    exact return (equality-constrained QP via SLSQP).
    """
    n = len(mean_returns)
    bounds, x0 = _base_constraints(n)

    lo = float(mean_returns.min())
    hi = float(mean_returns.max())
    targets = np.linspace(lo, hi, n_points)

    rows = []
    for target in targets:
        constraints = (
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
            {"type": "eq", "fun": lambda w, t=target: np.dot(w, mean_returns.values) - t},
        )
        result = minimize(
            _volatility, x0, args=(mean_returns, cov_matrix),
            method="SLSQP", bounds=bounds, constraints=constraints,
        )
        if result.success:
            ret, vol, sharpe = portfolio_performance(result.x, mean_returns, cov_matrix, risk_free_rate)
            rows.append({"return": ret, "volatility": vol, "sharpe": sharpe})
    return pd.DataFrame(rows).sort_values("volatility").reset_index(drop=True)
