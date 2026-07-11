"""
Monte Carlo NAV projection — Geometric Brownian Motion (GBM).

Calibrates drift (mu) and volatility (sigma) from a fund's historical daily
log-returns, then simulates many possible future NAV paths:

    NAV_t = NAV_0 * exp( cumsum( N(mu, sigma) draws ) )

This is the standard approach for simulating asset-price paths under the
random-walk assumption (returns are i.i.d. normal in log-space). It does NOT
predict the fund's actual future performance — it's a probabilistic range
of outcomes consistent with the fund's own historical mean return and
volatility, which is the honest way to present "uncertainty bands."
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252


@dataclass
class GBMParams:
    mu_daily: float          # mean daily log-return
    sigma_daily: float       # std dev of daily log-return
    mu_annual: float         # annualised drift
    sigma_annual: float      # annualised volatility
    n_obs: int                # number of historical observations used to calibrate


def calibrate_gbm(daily_returns: pd.Series) -> GBMParams:
    """Estimate GBM parameters from a series of simple daily returns
    (e.g. daily_return = nav.pct_change()).
    """
    clean = daily_returns.dropna()
    if len(clean) < 30:
        raise ValueError(f"Need at least 30 daily-return observations to calibrate; got {len(clean)}.")

    log_returns = np.log1p(clean)
    mu_daily = float(log_returns.mean())
    sigma_daily = float(log_returns.std(ddof=1))

    return GBMParams(
        mu_daily=mu_daily,
        sigma_daily=sigma_daily,
        mu_annual=mu_daily * TRADING_DAYS_PER_YEAR,
        sigma_annual=sigma_daily * np.sqrt(TRADING_DAYS_PER_YEAR),
        n_obs=len(clean),
    )


def simulate_gbm_paths(
    start_nav: float,
    params: GBMParams,
    years: int = 5,
    n_simulations: int = 2000,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
    seed: int | None = 42,
) -> np.ndarray:
    """Return an array of shape (n_simulations, n_days + 1) of simulated NAV paths.
    Column 0 is start_nav for every path (t=0).
    """
    n_days = years * trading_days_per_year
    rng = np.random.default_rng(seed)

    shocks = rng.normal(
        loc=params.mu_daily, scale=params.sigma_daily, size=(n_simulations, n_days)
    )
    log_paths = np.cumsum(shocks, axis=1)
    nav_paths = start_nav * np.exp(log_paths)

    paths = np.empty((n_simulations, n_days + 1))
    paths[:, 0] = start_nav
    paths[:, 1:] = nav_paths
    return paths


def summarize_paths(
    paths: np.ndarray,
    start_date: pd.Timestamp,
    trading_days_per_year: int = TRADING_DAYS_PER_YEAR,
    percentiles: tuple[int, ...] = (5, 25, 50, 75, 95),
) -> pd.DataFrame:
    """Collapse simulated paths into a percentile-band DataFrame, one row per trading day,
    with a real calendar date column (approximate — trading-day step, not calendar day).
    """
    n_days = paths.shape[1] - 1
    dates = pd.bdate_range(start=start_date, periods=n_days + 1, freq="B")

    pct_values = np.percentile(paths, percentiles, axis=0)  # shape (len(percentiles), n_days+1)

    data = {"date": dates, "day_index": np.arange(n_days + 1)}
    for p, vals in zip(percentiles, pct_values):
        data[f"p{p}"] = vals
    df = pd.DataFrame(data)
    return df


def risk_summary(paths: np.ndarray, start_nav: float) -> dict:
    """Headline risk/return stats for the final simulated day."""
    final = paths[:, -1]
    total_return_pct = (final / start_nav - 1) * 100
    n_years = None  # caller supplies context if needed

    return {
        "median_final_nav": float(np.median(final)),
        "mean_final_nav": float(np.mean(final)),
        "p5_final_nav": float(np.percentile(final, 5)),
        "p95_final_nav": float(np.percentile(final, 95)),
        "median_total_return_pct": float(np.median(total_return_pct)),
        "prob_loss_pct": float((final < start_nav).mean() * 100),
        "best_case_return_pct": float(np.percentile(total_return_pct, 95)),
        "worst_case_return_pct": float(np.percentile(total_return_pct, 5)),
    }
