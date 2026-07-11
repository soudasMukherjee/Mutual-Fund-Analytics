from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    cand = start
    for _ in range(12):
        if (cand / "Data" / "processed" / "daily_returns_all_schemes.csv").exists() and (
            cand / "Data" / "processed" / "fund_master_clean.csv"
        ).exists():
            return cand
        if cand.name == "notebooks":
            parent = cand.parent
            if (parent / "Data" / "processed" / "daily_returns_all_schemes.csv").exists() and (
                parent / "Data" / "processed" / "fund_master_clean.csv"
            ).exists():
                return parent
        cand = cand.parent
    return start.parent


REPO_ROOT = find_repo_root(Path(__file__).resolve())
DATA_DIR = REPO_ROOT / "Data" / "processed"

returns_path = DATA_DIR / "daily_returns_all_schemes.csv"
fund_path = DATA_DIR / "fund_master_clean.csv"
rank_path = DATA_DIR / "sharpe_sortino_ranked_rf6_5.csv"

for p in [returns_path, fund_path, rank_path]:
    if not p.exists():
        raise FileNotFoundError(f"Missing required file: {p.resolve()}")

returns_df = pd.read_csv(returns_path)
fund_df = pd.read_csv(fund_path)
rank_df = pd.read_csv(rank_path)

returns_df["date"] = pd.to_datetime(returns_df["date"], errors="coerce")
returns_df["amfi_code"] = pd.to_numeric(returns_df["amfi_code"], errors="coerce").astype("Int64")
returns_df["daily_return"] = pd.to_numeric(returns_df["daily_return"], errors="coerce")

fund_df["amfi_code"] = pd.to_numeric(fund_df["amfi_code"], errors="coerce").astype("Int64")

if "scheme_name" not in returns_df.columns:
    returns_df = returns_df.merge(
        fund_df[["amfi_code", "scheme_name"]], on="amfi_code", how="left"
    )

returns_df["scheme_name"] = returns_df["scheme_name"].astype(str)
returns_df = returns_df.dropna(subset=["amfi_code", "scheme_name", "daily_return", "date"]).copy()

rank_df["amfi_code"] = pd.to_numeric(rank_df["amfi_code"], errors="coerce").astype("Int64")
# some files might use different scheme name col casing
if "scheme_name" in rank_df.columns:
    rank_df["scheme_name"] = rank_df["scheme_name"].astype(str)

if "sharpe_ratio" not in rank_df.columns:
    raise ValueError("Expected column sharpe_ratio in sharpe_sortino_ranked_rf6_5.csv")

# Pick top 5 by sharpe_ratio
rank_df = rank_df.dropna(subset=["amfi_code", "sharpe_ratio"]).copy()

top5 = (
    rank_df.sort_values("sharpe_ratio", ascending=False)
    .head(5)[["amfi_code", "scheme_name"]]
)
top5_codes = set(top5["amfi_code"].dropna().astype(int).tolist())

print("Top 5 key funds (by Sharpe ratio from Day 4):")
print(top5.to_string(index=False))

returns_top5 = returns_df[returns_df["amfi_code"].isin(top5_codes)].copy()

RF_ANNUAL = 0.065
TRADING_DAYS = 252
ROLLING_DAYS = 90

rf_daily = RF_ANNUAL / TRADING_DAYS

returns_top5 = returns_top5.sort_values(["amfi_code", "date"]).copy()
returns_top5["excess_return"] = returns_top5["daily_return"] - rf_daily

g = returns_top5.groupby(["amfi_code", "scheme_name"], sort=False)["excess_return"]
rolling_mean = g.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).mean().reset_index(level=[0, 1], drop=True)
rolling_std = g.rolling(ROLLING_DAYS, min_periods=ROLLING_DAYS).std(ddof=1).reset_index(level=[0, 1], drop=True)

returns_top5["rolling_mean_90d"] = rolling_mean
returns_top5["rolling_std_90d"] = rolling_std
returns_top5["rolling_sharpe_90d"] = (returns_top5["rolling_mean_90d"] / returns_top5["rolling_std_90d"]) * np.sqrt(
    TRADING_DAYS
)

plot_df = returns_top5.dropna(subset=["rolling_sharpe_90d"]).copy()
print("Rolling Sharpe points:", len(plot_df))

fig = px.line(
    plot_df,
    x="date",
    y="rolling_sharpe_90d",
    color="scheme_name",
    title="Rolling 90-day Sharpe Ratio (Top 5 Funds) — Excess Returns",
    labels={"rolling_sharpe_90d": "Rolling Sharpe (90d)", "date": "Date", "scheme_name": "Fund"},
    template="plotly_white",
)
fig.update_layout(legend_title_text="Fund", hovermode="x unified")

# Save artifact for capstone deliverable (avoid kaleido dependency)
out_png = DATA_DIR / "rolling_sharpe_chart.html"
fig.write_html(str(out_png))
print("Saved:", out_png)

# Keep interactive view
fig.show()



latest = (
    plot_df.sort_values("date")
    .groupby(["amfi_code", "scheme_name"], as_index=False)
    .tail(1)[["amfi_code", "scheme_name", "date", "rolling_sharpe_90d"]]
    .sort_values("rolling_sharpe_90d", ascending=False)
)

print("Latest Rolling 90d Sharpe per fund:")
print(latest.to_string(index=False))

