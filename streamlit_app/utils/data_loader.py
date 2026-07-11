"""
Data access layer for the Bluestock MF Streamlit dashboard.

Primary source: ``bluestock_mf.db`` — the Day-2 SQLite star schema
(8 tables: dim_fund, dim_date, fact_nav, fact_transactions, fact_performance,
fact_aum, fact_portfolio, fact_sip_industry). This is the same DB Power BI
would connect to via ODBC/SQLite connector.

Fallback: the cleaned CSVs under Data/processed/ — used both if the SQLite
file is missing, and for the 3 industry-level datasets that were never loaded
into the warehouse (category_inflows, industry_folio_count, benchmark_indices).

All loaders are cached with st.cache_data / st.cache_resource so page
switches and slicer changes don't re-hit disk every time.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Repo-root detection — mirrors the pattern used in the Advanced Analytics
# notebook so this app works regardless of the current working directory.
# ---------------------------------------------------------------------------
def _find_repo_root(start: Path) -> Path:
    cand = start
    for _ in range(10):
        if (cand / "Data" / "processed").exists() and (cand / "bluestock_mf.db").exists():
            return cand
        cand = cand.parent
    # Fall back to just requiring Data/processed (DB may be regenerated elsewhere)
    cand = start
    for _ in range(10):
        if (cand / "Data" / "processed").exists():
            return cand
        cand = cand.parent
    raise FileNotFoundError("Could not locate the repo root (Data/processed not found).")


REPO_ROOT = _find_repo_root(Path(__file__).resolve())
DB_PATH = REPO_ROOT / "bluestock_mf.db"
PROCESSED_DIR = REPO_ROOT / "Data" / "processed"

EXPECTED_TABLES = [
    "dim_fund", "dim_date", "fact_nav", "fact_transactions",
    "fact_performance", "fact_aum", "fact_portfolio", "fact_sip_industry",
]


# ---------------------------------------------------------------------------
# Connection + table verification (task 1: "verify all 8 tables load")
# ---------------------------------------------------------------------------
@st.cache_resource
def get_connection() -> sqlite3.Connection | None:
    if not DB_PATH.exists():
        return None
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)


@st.cache_data(ttl=600)
def verify_data_connection() -> dict:
    """Connect to SQLite, confirm all 8 star-schema tables load, and report
    row counts + which relationship keys tie them together. Returns a dict
    the Home page renders as a status panel.
    """
    conn = get_connection()
    status = {
        "source": "sqlite" if conn is not None else "csv_fallback",
        "db_path": str(DB_PATH),
        "tables": {},
        "all_ok": True,
        "relationships": [
            ("dim_fund.amfi_code", "fact_nav.amfi_code"),
            ("dim_fund.amfi_code", "fact_transactions.amfi_code"),
            ("dim_fund.amfi_code", "fact_performance.amfi_code"),
            ("dim_fund.amfi_code", "fact_portfolio.amfi_code"),
            ("dim_date.date_id", "fact_nav.date_id"),
            ("dim_date.date_id", "fact_transactions.date_id"),
            ("dim_date.date_id", "fact_portfolio.date_id"),
            ("fact_aum.fund_house", "dim_fund.fund_house  (grain: fund-house level, not amfi_code)"),
        ],
    }

    if conn is None:
        status["all_ok"] = False
        for t in EXPECTED_TABLES:
            status["tables"][t] = {"loaded": False, "rows": 0, "error": "bluestock_mf.db not found"}
        return status

    for t in EXPECTED_TABLES:
        try:
            n = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
            status["tables"][t] = {"loaded": True, "rows": int(n), "error": None}
        except Exception as exc:  # noqa: BLE001
            status["tables"][t] = {"loaded": False, "rows": 0, "error": str(exc)}
            status["all_ok"] = False

    return status


# ---------------------------------------------------------------------------
# Core loaders (SQLite, joined back to a flat/dated shape for convenience)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_dim_fund() -> pd.DataFrame:
    conn = get_connection()
    if conn is not None:
        return pd.read_sql("SELECT * FROM dim_fund", conn)
    return pd.read_csv(PROCESSED_DIR / "fund_master_clean.csv")


@st.cache_data(ttl=600)
def load_fact_performance() -> pd.DataFrame:
    conn = get_connection()
    if conn is not None:
        df = pd.read_sql(
            """
            SELECT p.*, f.fund_house, f.scheme_name, f.category, f.plan, f.sub_category, f.benchmark
            FROM fact_performance p
            JOIN dim_fund f ON f.amfi_code = p.amfi_code
            """,
            conn,
        )
        return df
    return pd.read_csv(PROCESSED_DIR / "scheme_performance_clean.csv")


@st.cache_data(ttl=600)
def load_fact_nav() -> pd.DataFrame:
    """Daily NAV per scheme, joined to a real date column."""
    conn = get_connection()
    if conn is not None:
        df = pd.read_sql(
            """
            SELECT n.amfi_code, d.full_date AS date, n.nav, n.daily_return_pct
            FROM fact_nav n
            JOIN dim_date d ON d.date_id = n.date_id
            """,
            conn,
        )
    else:
        df = pd.read_csv(PROCESSED_DIR / "nav_history_clean.csv")
        df = df.rename(columns={c: c for c in df.columns})
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=600)
def load_fact_transactions() -> pd.DataFrame:
    conn = get_connection()
    if conn is not None:
        df = pd.read_sql(
            """
            SELECT t.*, d.full_date AS transaction_date
            FROM fact_transactions t
            JOIN dim_date d ON d.date_id = t.date_id
            """,
            conn,
        )
    else:
        df = pd.read_csv(PROCESSED_DIR / "investor_transactions_clean.csv")
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    return df


@st.cache_data(ttl=600)
def load_fact_aum() -> pd.DataFrame:
    conn = get_connection()
    if conn is not None:
        df = pd.read_sql(
            """
            SELECT a.*, d.full_date AS date
            FROM fact_aum a
            JOIN dim_date d ON d.date_id = a.date_id
            """,
            conn,
        )
    else:
        df = pd.read_csv(PROCESSED_DIR / "aum_by_fund_house_clean.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=600)
def load_fact_sip_industry() -> pd.DataFrame:
    conn = get_connection()
    if conn is not None:
        df = pd.read_sql("SELECT * FROM fact_sip_industry", conn)
    else:
        df = pd.read_csv(PROCESSED_DIR / "monthly_sip_inflows_clean.csv")
        df = df.rename(columns={"month": "year_month"})
    return df


@st.cache_data(ttl=600)
def load_fact_portfolio() -> pd.DataFrame:
    conn = get_connection()
    if conn is not None:
        df = pd.read_sql(
            """
            SELECT h.*, d.full_date AS date
            FROM fact_portfolio h
            JOIN dim_date d ON d.date_id = h.date_id
            """,
            conn,
        )
    else:
        df = pd.read_csv(PROCESSED_DIR / "portfolio_holdings_clean.csv")
    return df


# ---------------------------------------------------------------------------
# Industry-level CSVs not present in the warehouse (kept as CSV by design)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600)
def load_category_inflows() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "category_inflows_clean.csv")


@st.cache_data(ttl=600)
def load_folio_counts() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "industry_folio_count_clean.csv")


@st.cache_data(ttl=600)
def load_benchmark_indices() -> pd.DataFrame:
    df = pd.read_csv(PROCESSED_DIR / "benchmark_indices_clean.csv")
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data(ttl=600)
def load_fund_scorecard() -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / "fund_scorecard.csv")


@st.cache_data(ttl=600)
def load_daily_returns_long() -> pd.DataFrame:
    """Long-format (date, amfi_code, scheme_name, nav, daily_return) daily-return
    table used by the Efficient Frontier optimiser. Prefers the pre-computed
    Day-4 CSV; falls back to deriving it from fact_nav + dim_fund if missing.
    """
    precomputed = PROCESSED_DIR / "daily_returns_all_schemes.csv"
    if precomputed.exists():
        df = pd.read_csv(precomputed)
        df["date"] = pd.to_datetime(df["date"])
        return df

    nav_df = load_fact_nav()
    fund_df = load_dim_fund()[["amfi_code", "scheme_name"]]
    merged = nav_df.merge(fund_df, on="amfi_code", how="left").sort_values(["scheme_name", "date"])
    merged["daily_return"] = merged.groupby("scheme_name")["nav"].pct_change()
    return merged


# Fund benchmark text (e.g. "NIFTY 50 TRI") -> index_name key in benchmark_indices_clean
BENCHMARK_NAME_TO_INDEX = {
    "NIFTY 50 TRI": "NIFTY50",
    "NIFTY 100 TRI": "NIFTY100",
    "NIFTY 500 TRI": "NIFTY500",
    "NIFTY Midcap 150 TRI": "NIFTY_MIDCAP150",
    "BSE 250 SmallCap TRI": "BSE_SMALLCAP",
    "CRISIL Liquid Fund AI Index": "CRISIL_LIQUID",
    "CRISIL Dynamic Gilt Index": "CRISIL_GILT",
    # No exact matching index series in benchmark_indices_clean.csv for these:
    "CRISIL Short Term Bond Index": None,
    "NIFTY Midcap 50 TRI": None,
    "NIFTY Large Midcap 250 TRI": None,
}
