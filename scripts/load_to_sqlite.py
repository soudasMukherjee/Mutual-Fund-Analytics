"""
Day 2 — Load cleaned datasets into the SQLite star schema.
===========================================================
Reads the schema from sql/schema.sql, builds dim_date from the NAV history
date range, and loads every cleaned CSV in Data/processed/ into its
corresponding dimension/fact table using SQLAlchemy + df.to_sql().

Run directly:
    python scripts/load_to_sqlite.py

After loading, verifies row counts against the source CSVs and prints a
summary table.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"
SQL_DIR = PROJECT_ROOT / "sql"
DB_PATH = PROJECT_ROOT / "bluestock_mf.db"

DOW_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def build_dim_date(start: str, end: str) -> pd.DataFrame:
    """Build one row per calendar day between start and end (inclusive)."""
    dates = pd.date_range(start=start, end=end, freq="D")
    df = pd.DataFrame({"full_date": dates})
    df["date_id"] = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["year"] = df["full_date"].dt.year
    df["quarter"] = df["full_date"].dt.quarter
    df["month"] = df["full_date"].dt.month
    df["month_name"] = df["full_date"].dt.month.map(lambda m: MONTH_NAMES[m - 1])
    df["year_month"] = df["full_date"].dt.strftime("%Y-%m")
    df["day"] = df["full_date"].dt.day
    df["day_of_week"] = df["full_date"].dt.dayofweek.map(lambda d: DOW_NAMES[d])
    df["is_weekday"] = (df["full_date"].dt.dayofweek < 5).astype(int)
    df["full_date"] = df["full_date"].dt.strftime("%Y-%m-%d")
    return df[
        ["date_id", "full_date", "year", "quarter", "month", "month_name",
         "year_month", "day", "day_of_week", "is_weekday"]
    ]


def to_date_id(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.strftime("%Y%m%d").astype(int)


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    engine = create_engine(f"sqlite:///{DB_PATH}")

    # --- 1. Create schema ---
    schema_sql = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    with engine.begin() as conn:
        for statement in schema_sql.split(";"):
            stmt = statement.strip()
            if stmt:
                conn.execute(text(stmt))

    verification: dict[str, dict] = {}

    # --- 2. dim_fund ---
    fund_master = pd.read_csv(PROCESSED_DIR / "fund_master_clean.csv")
    fund_master.to_sql("dim_fund", engine, if_exists="append", index=False)
    verification["dim_fund"] = {"source_rows": len(fund_master), "table": "dim_fund"}

    # --- 3. dim_date (spans full NAV history range) ---
    nav_history = pd.read_csv(PROCESSED_DIR / "nav_history_clean.csv")
    dim_date = build_dim_date(nav_history["date"].min(), nav_history["date"].max())
    dim_date.to_sql("dim_date", engine, if_exists="append", index=False)
    verification["dim_date"] = {"source_rows": len(dim_date), "table": "dim_date"}

    # --- 4. fact_nav ---
    fact_nav = nav_history.copy()
    fact_nav["date_id"] = to_date_id(fact_nav["date"])
    fact_nav = fact_nav[["amfi_code", "date_id", "nav"]]
    # daily_return_pct computed per-fund in pandas (NAV_t / NAV_t-1 - 1), faster
    # and clearer than a correlated subquery, then loaded alongside nav.
    fact_nav = fact_nav.sort_values(["amfi_code", "date_id"])
    fact_nav["daily_return_pct"] = (
        fact_nav.groupby("amfi_code")["nav"].pct_change() * 100
    ).round(6)
    fact_nav.to_sql("fact_nav", engine, if_exists="append", index=False)
    verification["fact_nav"] = {"source_rows": len(nav_history), "table": "fact_nav"}

    # --- 5. fact_transactions ---
    transactions = pd.read_csv(PROCESSED_DIR / "investor_transactions_clean.csv")
    fact_tx = transactions.copy()
    fact_tx["date_id"] = to_date_id(fact_tx["transaction_date"])
    fact_tx = fact_tx.drop(columns=["transaction_date"])
    cols = [
        "investor_id", "date_id", "amfi_code", "transaction_type", "amount_inr",
        "state", "city", "city_tier", "age_group", "gender",
        "annual_income_lakh", "payment_mode", "kyc_status",
    ]
    fact_tx = fact_tx[[c for c in cols if c in fact_tx.columns]]
    fact_tx.to_sql("fact_transactions", engine, if_exists="append", index=False)
    verification["fact_transactions"] = {"source_rows": len(transactions), "table": "fact_transactions"}

    # --- 6. fact_performance ---
    performance = pd.read_csv(PROCESSED_DIR / "scheme_performance_clean.csv")
    fact_perf = performance[
        [
            "amfi_code", "return_1yr_pct", "return_3yr_pct", "return_5yr_pct",
            "benchmark_3yr_pct", "alpha", "beta", "sharpe_ratio", "sortino_ratio",
            "std_dev_ann_pct", "max_drawdown_pct", "aum_crore", "expense_ratio_pct",
            "morningstar_rating", "risk_grade",
        ]
    ].copy()
    if "data_quality_flag" in performance.columns:
        fact_perf["data_quality_flag"] = performance["data_quality_flag"]
    else:
        fact_perf["data_quality_flag"] = None
    fact_perf.to_sql("fact_performance", engine, if_exists="append", index=False)
    verification["fact_performance"] = {"source_rows": len(performance), "table": "fact_performance"}

    # --- 7. fact_aum ---
    aum = pd.read_csv(PROCESSED_DIR / "aum_by_fund_house_clean.csv")
    fact_aum = aum.copy()
    fact_aum["date_id"] = to_date_id(fact_aum["date"])
    fact_aum = fact_aum[["date_id", "fund_house", "aum_lakh_crore", "aum_crore", "num_schemes"]]
    fact_aum.to_sql("fact_aum", engine, if_exists="append", index=False)
    verification["fact_aum"] = {"source_rows": len(aum), "table": "fact_aum"}

    # --- 8. fact_portfolio (bonus) ---
    holdings = pd.read_csv(PROCESSED_DIR / "portfolio_holdings_clean.csv")
    fact_portfolio = holdings.copy()
    fact_portfolio["date_id"] = to_date_id(fact_portfolio["portfolio_date"])
    fact_portfolio = fact_portfolio[
        ["amfi_code", "date_id", "stock_symbol", "stock_name", "sector",
         "weight_pct", "market_value_cr", "current_price_inr"]
    ]
    fact_portfolio.to_sql("fact_portfolio", engine, if_exists="append", index=False)
    verification["fact_portfolio"] = {"source_rows": len(holdings), "table": "fact_portfolio"}

    # --- 9. fact_sip_industry (bonus) ---
    sip = pd.read_csv(PROCESSED_DIR / "monthly_sip_inflows_clean.csv")
    fact_sip = sip.rename(columns={"month": "year_month"})[
        ["year_month", "sip_inflow_crore", "active_sip_accounts_crore",
         "new_sip_accounts_lakh", "sip_aum_lakh_crore", "yoy_growth_pct"]
    ]
    fact_sip.to_sql("fact_sip_industry", engine, if_exists="append", index=False)
    verification["fact_sip_industry"] = {"source_rows": len(sip), "table": "fact_sip_industry"}

    # --- 10. Verify row counts in DB match source CSVs ---
    print(f"{'Table':22s} {'Source rows':>12s} {'DB rows':>10s}  Match")
    print("-" * 60)
    all_match = True
    with engine.connect() as conn:
        for name, info in verification.items():
            db_count = conn.execute(text(f"SELECT COUNT(*) FROM {info['table']}")).scalar()
            match = db_count == info["source_rows"]
            all_match &= match
            print(f"{info['table']:22s} {info['source_rows']:>12,} {db_count:>10,}  {'OK' if match else 'MISMATCH'}")

    print("-" * 60)
    print("ALL ROW COUNTS MATCH" if all_match else "ROW COUNT MISMATCH DETECTED — investigate above")
    print(f"\nDatabase written to: {DB_PATH}")


if __name__ == "__main__":
    main()
