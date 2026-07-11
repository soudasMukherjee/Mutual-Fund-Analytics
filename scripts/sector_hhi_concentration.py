from __future__ import annotations

"""Sector concentration via HHI.

User request:
- Compute Sector HHI per fund: HHI = Σ(weight_i^2) where weights are
  sector weights within the fund.
- Higher HHI => more concentrated portfolio.

Inputs (Data/processed):
- portfolio_holdings_clean.csv (contains sector + weight_pct)

Output:
- Data/processed/sector_hhi_by_fund.csv

Run:
- python scripts/sector_hhi_concentration.py

Notes:
- Uses the most recent portfolio_date per fund (highest portfolio_date).
- weight_pct is expected in percentage units (0-100). We convert to fractions
  before squaring.
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"


def main() -> None:
    holdings_path = PROCESSED_DIR / "portfolio_holdings_clean.csv"
    out_path = PROCESSED_DIR / "sector_hhi_by_fund.csv"

    if not holdings_path.exists():
        raise FileNotFoundError(f"Missing input: {holdings_path}")

    df = pd.read_csv(holdings_path)

    required = {"amfi_code", "portfolio_date", "sector", "weight_pct"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"portfolio_holdings_clean.csv missing columns: {sorted(missing)}")

    df["portfolio_date"] = pd.to_datetime(df["portfolio_date"], errors="coerce")
    df["weight_pct"] = pd.to_numeric(df["weight_pct"], errors="coerce")
    df = df.dropna(subset=["portfolio_date", "amfi_code", "sector", "weight_pct"]).copy()

    # Most recent date per fund
    idx = df.groupby("amfi_code")["portfolio_date"].transform("max")
    recent = df[df["portfolio_date"] == idx].copy()

    # Normalize sector weights to sum to 1 per fund (since weight_pct may not be exactly 100)
    recent["weight_frac"] = recent["weight_pct"] / 100.0
    denom = recent.groupby("amfi_code")["weight_frac"].transform("sum")
    recent = recent[denom > 0].copy()
    recent["weight_frac"] = recent["weight_frac"] / recent.groupby("amfi_code")["weight_frac"].transform("sum")

    # HHI
    recent["weight_sq"] = recent["weight_frac"] ** 2
    hhi = recent.groupby("amfi_code").agg(
        hhi_sector_concentration=("weight_sq", "sum"),
        sector_count=("sector", "nunique"),
        portfolio_date=("portfolio_date", "max"),
    ).reset_index()

    # Attach scheme_name
    fund_path = PROCESSED_DIR / "fund_master_clean.csv"
    if fund_path.exists():
        fund_df = pd.read_csv(fund_path)
        if "scheme_name" in fund_df.columns:
            hhi = hhi.merge(fund_df[["amfi_code", "scheme_name"]].drop_duplicates(), on="amfi_code", how="left")

    hhi = hhi.sort_values("hhi_sector_concentration", ascending=False).reset_index(drop=True)
    hhi.to_csv(out_path, index=False)

    print(f"Wrote: {out_path} ({len(hhi)} funds)\n")
    print(hhi.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

