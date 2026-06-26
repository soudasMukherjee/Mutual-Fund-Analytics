"""
Day 2 — Data Cleaning Pipeline
==============================
Cleans all 10 raw Bluestock MF Capstone datasets and writes the results to
``Data/processed/``. Produces one cleaning report (JSON) per dataset
describing exactly what was dropped, fixed, or flagged.

Run directly:
    python scripts/clean_all_datasets.py

Three datasets get full validation/transformation logic per the Day 2 brief:
    1. nav_history            -> parse dates, sort, forward-fill, dedupe, validate NAV > 0
    2. investor_transactions  -> standardise transaction_type/kyc_status, validate amount > 0, fix dates
    3. scheme_performance     -> validate numeric returns, flag anomalies, check expense_ratio range

The remaining 7 datasets (fund_master, aum_by_fund_house, monthly_sip_inflows,
category_inflows, industry_folio_count, portfolio_holdings, benchmark_indices)
get a lighter but still real cleaning pass: type coercion, date parsing,
duplicate removal, and null/negative-value checks, since they feed directly
into the star schema and dashboard.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "Data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"


def _norm_str_series(s: pd.Series) -> pd.Series:
    """Trim, collapse inner whitespace, and uppercase a string series for robust matching."""
    return (
        s.astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.upper()
    )


def _write(df: pd.DataFrame, report: dict, csv_name: str, report_name: str) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(PROCESSED_DIR / csv_name, index=False)
    (PROCESSED_DIR / report_name).write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. nav_history.csv
# ---------------------------------------------------------------------------
def clean_nav_history(raw_path: Path = RAW_DIR / "02_nav_history.csv") -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(raw_path)

    expected_cols = {"amfi_code", "date", "nav"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {raw_path}: {sorted(missing)}")

    df = df[["amfi_code", "date", "nav"]].copy()
    report: dict[str, object] = {"input_path": str(raw_path), "before_rows": len(df)}

    # --- Parse types ---
    df["amfi_code"] = pd.to_numeric(df["amfi_code"], errors="coerce").astype("Int64")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    invalid_date_rows = int(df["date"].isna().sum())
    invalid_code_rows = int(df["amfi_code"].isna().sum())
    df = df.dropna(subset=["amfi_code", "date"]).copy()

    invalid_nav_rows = int(df["nav"].isna().sum())
    df = df.dropna(subset=["nav"]).copy()

    after_type_rows = len(df)
    df["amfi_code"] = df["amfi_code"].astype(int)

    # --- Sort by amfi_code + date, then de-duplicate ---
    df = df.sort_values(["amfi_code", "date", "nav"], kind="mergesort")
    dup_mask = df.duplicated(subset=["amfi_code", "date"], keep="first")
    duplicate_rows_removed = int(dup_mask.sum())
    df = df.loc[~dup_mask].copy()

    # --- Forward-fill missing NAV across the full calendar-day range per fund ---
    # AMFI publishes NAV on business days only; weekends/holidays are filled
    # forward from the most recent published value, per brief instructions.
    filled_frames = []
    total_filled_rows = 0

    for amfi_code, g in df.groupby("amfi_code", sort=False):
        g = g.sort_values("date")
        full_idx = pd.date_range(start=g["date"].min(), end=g["date"].max(), freq="D")
        g2 = g.set_index("date")[["nav"]].reindex(full_idx)

        missing_before = int(g2["nav"].isna().sum())
        g2["nav"] = g2["nav"].ffill()
        missing_after = int(g2["nav"].isna().sum())
        total_filled_rows += max(0, missing_before - missing_after)

        g2 = g2.reset_index().rename(columns={"index": "date"})
        g2["amfi_code"] = amfi_code
        filled_frames.append(g2)

    out = pd.concat(filled_frames, ignore_index=True)
    out = out.sort_values(["amfi_code", "date"], kind="mergesort").reset_index(drop=True)

    # --- Validate NAV > 0 ---
    non_positive_rows = int((out["nav"] <= 0).sum())
    out = out.dropna(subset=["nav"])
    out = out[out["nav"] > 0].copy()

    out["amfi_code"] = out["amfi_code"].astype(int)
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    out = out[["amfi_code", "date", "nav"]]

    report.update(
        {
            "invalid_date_rows_dropped": invalid_date_rows,
            "invalid_amfi_code_rows_dropped": invalid_code_rows,
            "invalid_nav_rows_dropped": invalid_nav_rows,
            "after_type_coercion_rows": after_type_rows,
            "duplicate_rows_removed_by_amfi_code_date": duplicate_rows_removed,
            "calendar_day_rows_forward_filled": total_filled_rows,
            "non_positive_nav_rows_removed": non_positive_rows,
            "output_rows": len(out),
            "unique_funds": int(out["amfi_code"].nunique()),
            "date_range": [out["date"].min(), out["date"].max()],
        }
    )
    return out, report


# ---------------------------------------------------------------------------
# 2. investor_transactions.csv
# ---------------------------------------------------------------------------
def clean_investor_transactions(
    raw_path: Path = PROCESSED_DIR / "08_investor_transactions.csv",
) -> tuple[pd.DataFrame, dict]:
    # Note: the source file ships in Data/processed/ (not Data/raw/) in this
    # project snapshot — it is the raw/un-cleaned export, just placed there.
    df = pd.read_csv(raw_path)

    required = {"transaction_date", "transaction_type", "amount_inr", "kyc_status"}
    missing_required = required - set(df.columns)
    if missing_required:
        raise ValueError(f"Missing required columns: {sorted(missing_required)}")

    report: dict[str, object] = {"input_path": str(raw_path), "before_rows": len(df)}

    # --- transaction_type: standardise to SIP / Lumpsum / Redemption ---
    t = _norm_str_series(df["transaction_type"])
    type_map = {
        "SIP": "SIP",
        "LUMPSUM": "Lumpsum",
        "LUMP SUM": "Lumpsum",
        "REDEMPTION": "Redemption",
        "REDEMP": "Redemption",
    }
    df["transaction_type"] = t.map(type_map)
    unmapped_type_rows = int(df["transaction_type"].isna().sum())
    df["transaction_type"] = df["transaction_type"].fillna("Unknown")

    # --- transaction_date: fix/parse date formats ---
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    invalid_date_rows = int(df["transaction_date"].isna().sum())
    df = df.dropna(subset=["transaction_date"]).copy()

    # --- amount_inr: validate > 0 ---
    df["amount_inr"] = pd.to_numeric(df["amount_inr"], errors="coerce")
    invalid_amount_rows = int(df["amount_inr"].isna().sum())
    df = df.dropna(subset=["amount_inr"]).copy()
    non_positive_amount_rows = int((df["amount_inr"] <= 0).sum())
    df = df[df["amount_inr"] > 0].copy()
    df["amount_inr"] = df["amount_inr"].astype(int)

    # --- kyc_status: check enum values (Verified / Pending) ---
    k = _norm_str_series(df["kyc_status"])
    kyc_map = {"VERIFIED": "Verified", "PENDING": "Pending"}
    df["kyc_status"] = k.map(kyc_map)
    invalid_kyc_rows = int(df["kyc_status"].isna().sum())
    df["kyc_status"] = df["kyc_status"].fillna("Unknown")

    # --- amfi_code: numeric FK ---
    if "amfi_code" in df.columns:
        df["amfi_code"] = pd.to_numeric(df["amfi_code"], errors="coerce").astype("Int64")
        invalid_amfi_rows = int(df["amfi_code"].isna().sum())
        df = df.dropna(subset=["amfi_code"]).copy()
        df["amfi_code"] = df["amfi_code"].astype(int)
    else:
        invalid_amfi_rows = 0

    # --- light text standardisation on remaining categorical columns ---
    if "investor_id" in df.columns:
        df["investor_id"] = df["investor_id"].astype("string").str.strip()
    for col in ("state", "city", "city_tier", "age_group", "gender", "payment_mode"):
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    # --- duplicate full-row removal ---
    before_dedupe = len(df)
    df = df.drop_duplicates()
    duplicate_rows_removed = before_dedupe - len(df)

    df["transaction_date"] = df["transaction_date"].dt.strftime("%Y-%m-%d")

    sort_cols = [c for c in ["investor_id", "transaction_date", "amfi_code"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    report.update(
        {
            "unmapped_transaction_type_set_to_unknown": unmapped_type_rows,
            "invalid_transaction_date_rows_dropped": invalid_date_rows,
            "invalid_amount_inr_rows_dropped": invalid_amount_rows,
            "non_positive_amount_inr_rows_removed": non_positive_amount_rows,
            "unmapped_kyc_status_set_to_unknown": invalid_kyc_rows,
            "invalid_amfi_code_rows_dropped": invalid_amfi_rows,
            "duplicate_rows_removed": duplicate_rows_removed,
            "output_rows": len(df),
            "transaction_type_value_counts": df["transaction_type"].value_counts(dropna=False).to_dict(),
            "kyc_status_value_counts": df["kyc_status"].value_counts(dropna=False).to_dict(),
        }
    )
    return df, report


# ---------------------------------------------------------------------------
# 3. scheme_performance.csv
# ---------------------------------------------------------------------------
def clean_scheme_performance(
    raw_path: Path = RAW_DIR / "07_scheme_performance.csv",
) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(raw_path)
    report: dict[str, object] = {"input_path": str(raw_path), "before_rows": len(df)}

    numeric_cols = [
        "return_1yr_pct",
        "return_3yr_pct",
        "return_5yr_pct",
        "benchmark_3yr_pct",
        "alpha",
        "beta",
        "sharpe_ratio",
        "sortino_ratio",
        "std_dev_ann_pct",
        "max_drawdown_pct",
        "aum_crore",
        "expense_ratio_pct",
        "morningstar_rating",
    ]
    numeric_cols = [c for c in numeric_cols if c in df.columns]

    non_numeric_counts: dict[str, int] = {}
    for col in numeric_cols:
        before_na = df[col].isna().sum()
        df[col] = pd.to_numeric(df[col], errors="coerce")
        after_na = df[col].isna().sum()
        non_numeric_counts[col] = int(after_na - before_na)

    # --- amfi_code as int FK ---
    df["amfi_code"] = pd.to_numeric(df["amfi_code"], errors="coerce").astype("Int64")
    invalid_amfi_rows = int(df["amfi_code"].isna().sum())
    df = df.dropna(subset=["amfi_code"]).copy()
    df["amfi_code"] = df["amfi_code"].astype(int)

    # --- duplicate amfi_code rows ---
    before_dedupe = len(df)
    dup_mask = df.duplicated(subset=["amfi_code"], keep="first")
    duplicate_rows_removed = int(dup_mask.sum())
    df = df.loc[~dup_mask].copy()

    # --- anomaly flags (kept in output, not dropped, so analysts can review) ---
    flags = pd.Series([""] * len(df), index=df.index, dtype="object")

    def _flag(mask: pd.Series, label: str) -> None:
        nonlocal flags
        flags.loc[mask] = flags.loc[mask].where(flags.loc[mask] == "", flags.loc[mask] + "; ") + label
        flags.loc[mask & (flags == label)] = label  # no-op safeguard for clarity

    # Negative Sharpe / Sortino are real (means the fund underperformed risk-free), but
    # extreme outliers (|value| > 5) are very unusual for these ratios -> flag.
    if "sharpe_ratio" in df.columns:
        mask = df["sharpe_ratio"].abs() > 5
        flags.loc[mask] = (flags.loc[mask] + "; extreme_sharpe").str.strip("; ")
    if "sortino_ratio" in df.columns:
        mask = df["sortino_ratio"].abs() > 8
        flags.loc[mask] = (flags.loc[mask] + "; extreme_sortino").str.strip("; ")
    if "beta" in df.columns:
        mask = (df["beta"] < 0) | (df["beta"] > 3)
        flags.loc[mask] = (flags.loc[mask] + "; beta_out_of_range").str.strip("; ")
    if "max_drawdown_pct" in df.columns:
        mask = (df["max_drawdown_pct"] > 0) | (df["max_drawdown_pct"] < -90)
        flags.loc[mask] = (flags.loc[mask] + "; drawdown_out_of_range").str.strip("; ")
    if {"return_1yr_pct", "return_3yr_pct"}.issubset(df.columns):
        mask = (df["return_1yr_pct"].abs() > 200) | (df["return_3yr_pct"].abs() > 100)
        flags.loc[mask] = (flags.loc[mask] + "; extreme_return").str.strip("; ")

    # --- expense_ratio_pct range check: 0.1% - 2.5% per brief ---
    out_of_range_mask = pd.Series(False, index=df.index)
    if "expense_ratio_pct" in df.columns:
        out_of_range_mask = (df["expense_ratio_pct"] < 0.1) | (df["expense_ratio_pct"] > 2.5)
        flags.loc[out_of_range_mask] = (
            flags.loc[out_of_range_mask] + "; expense_ratio_out_of_range"
        ).str.strip("; ")

    df["data_quality_flag"] = flags.replace("", np.nan)

    report.update(
        {
            "non_numeric_values_coerced_to_nan_by_column": non_numeric_counts,
            "invalid_amfi_code_rows_dropped": invalid_amfi_rows,
            "duplicate_amfi_code_rows_removed": duplicate_rows_removed,
            "expense_ratio_out_of_range_0.1_to_2.5_pct": int(out_of_range_mask.sum()),
            "rows_with_any_anomaly_flag": int(df["data_quality_flag"].notna().sum()),
            "output_rows": len(df),
        }
    )

    df = df.sort_values("amfi_code").reset_index(drop=True)
    return df, report


# ---------------------------------------------------------------------------
# Generic light-cleaning pass for the remaining 7 reference/fact datasets
# ---------------------------------------------------------------------------
def _light_clean(
    raw_path: Path,
    date_cols: list[str] | None = None,
    numeric_cols: list[str] | None = None,
    dedupe_subset: list[str] | None = None,
    nonneg_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(raw_path)
    report: dict[str, object] = {"input_path": str(raw_path), "before_rows": len(df)}

    for col in date_cols or []:
        if col in df.columns:
            before_na = df[col].isna().sum()
            df[col] = pd.to_datetime(df[col], errors="coerce")
            invalid = int(df[col].isna().sum() - before_na)
            report[f"invalid_{col}_coerced"] = invalid

    for col in numeric_cols or []:
        if col in df.columns:
            before_na = df[col].isna().sum()
            df[col] = pd.to_numeric(df[col], errors="coerce")
            invalid = int(df[col].isna().sum() - before_na)
            report[f"non_numeric_{col}_coerced"] = invalid

    before_dedupe = len(df)
    df = df.drop_duplicates()
    report["duplicate_rows_removed"] = before_dedupe - len(df)

    negative_flags = {}
    for col in nonneg_cols or []:
        if col in df.columns:
            negative_flags[col] = int((df[col] < 0).sum())
    if negative_flags:
        report["negative_value_counts_by_column"] = negative_flags

    for col in date_cols or []:
        if col in df.columns:
            df[col] = df[col].dt.strftime("%Y-%m-%d")

    report["output_rows"] = len(df)
    return df, report


def clean_fund_master() -> tuple[pd.DataFrame, dict]:
    df, report = _light_clean(
        RAW_DIR / "01_fund_master.csv",
        date_cols=["launch_date"],
        numeric_cols=["expense_ratio_pct", "exit_load_pct", "min_sip_amount", "min_lumpsum_amount"],
        nonneg_cols=["expense_ratio_pct", "exit_load_pct", "min_sip_amount", "min_lumpsum_amount"],
    )
    df["amfi_code"] = pd.to_numeric(df["amfi_code"], errors="coerce").astype("Int64").astype(int)
    df = df.drop_duplicates(subset=["amfi_code"]).sort_values("amfi_code").reset_index(drop=True)
    return df, report


def clean_aum_by_fund_house() -> tuple[pd.DataFrame, dict]:
    df, report = _light_clean(
        RAW_DIR / "03_aum_by_fund_house.csv",
        date_cols=["date"],
        numeric_cols=["aum_lakh_crore", "aum_crore", "num_schemes"],
        nonneg_cols=["aum_lakh_crore", "aum_crore", "num_schemes"],
    )
    df = df.sort_values(["date", "fund_house"]).reset_index(drop=True)
    return df, report


def clean_monthly_sip_inflows() -> tuple[pd.DataFrame, dict]:
    df, report = _light_clean(
        RAW_DIR / "04_monthly_sip_inflows.csv",
        numeric_cols=["sip_inflow_crore", "active_sip_accounts_crore", "new_sip_accounts_lakh", "sip_aum_lakh_crore", "yoy_growth_pct"],
        nonneg_cols=["sip_inflow_crore", "active_sip_accounts_crore", "new_sip_accounts_lakh", "sip_aum_lakh_crore"],
    )
    df = df.sort_values("month").reset_index(drop=True)
    return df, report


def clean_category_inflows() -> tuple[pd.DataFrame, dict]:
    df, report = _light_clean(
        RAW_DIR / "05_category_inflows.csv",
        numeric_cols=["net_inflow_crore"],
    )
    df = df.sort_values(["month", "category"]).reset_index(drop=True)
    return df, report


def clean_industry_folio_count() -> tuple[pd.DataFrame, dict]:
    df, report = _light_clean(
        RAW_DIR / "06_industry_folio_count.csv",
        numeric_cols=["total_folios_crore", "equity_folios_crore", "debt_folios_crore", "hybrid_folios_crore", "others_folios_crore"],
        nonneg_cols=["total_folios_crore", "equity_folios_crore", "debt_folios_crore", "hybrid_folios_crore", "others_folios_crore"],
    )
    df = df.sort_values("month").reset_index(drop=True)
    return df, report


def clean_portfolio_holdings() -> tuple[pd.DataFrame, dict]:
    df, report = _light_clean(
        RAW_DIR / "09_portfolio_holdings.csv",
        date_cols=["portfolio_date"],
        numeric_cols=["weight_pct", "market_value_cr", "current_price_inr"],
        nonneg_cols=["weight_pct", "market_value_cr", "current_price_inr"],
    )
    df["amfi_code"] = pd.to_numeric(df["amfi_code"], errors="coerce").astype("Int64").astype(int)
    df = df.sort_values(["amfi_code", "weight_pct"], ascending=[True, False]).reset_index(drop=True)
    return df, report


def clean_benchmark_indices() -> tuple[pd.DataFrame, dict]:
    df, report = _light_clean(
        RAW_DIR / "10_benchmark_indices.csv",
        date_cols=["date"],
        numeric_cols=["close_value"],
        nonneg_cols=["close_value"],
        dedupe_subset=["date", "index_name"],
    )
    before = len(df)
    df = df.drop_duplicates(subset=["date", "index_name"], keep="first")
    report["duplicate_date_index_rows_removed_extra"] = before - len(df)
    df = df.sort_values(["index_name", "date"]).reset_index(drop=True)
    return df, report


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    summary = {}

    print("Cleaning 02_nav_history.csv ...")
    nav_df, nav_report = clean_nav_history()
    _write(nav_df, nav_report, "nav_history_clean.csv", "nav_history_clean_report.json")
    summary["nav_history"] = nav_report["output_rows"]

    print("Cleaning 08_investor_transactions.csv ...")
    tx_df, tx_report = clean_investor_transactions()
    _write(tx_df, tx_report, "investor_transactions_clean.csv", "investor_transactions_clean_report.json")
    summary["investor_transactions"] = tx_report["output_rows"]

    print("Cleaning 07_scheme_performance.csv ...")
    perf_df, perf_report = clean_scheme_performance()
    _write(perf_df, perf_report, "scheme_performance_clean.csv", "scheme_performance_clean_report.json")
    summary["scheme_performance"] = perf_report["output_rows"]

    print("Cleaning 01_fund_master.csv ...")
    fm_df, fm_report = clean_fund_master()
    _write(fm_df, fm_report, "fund_master_clean.csv", "fund_master_clean_report.json")
    summary["fund_master"] = fm_report["output_rows"]

    print("Cleaning 03_aum_by_fund_house.csv ...")
    aum_df, aum_report = clean_aum_by_fund_house()
    _write(aum_df, aum_report, "aum_by_fund_house_clean.csv", "aum_by_fund_house_clean_report.json")
    summary["aum_by_fund_house"] = aum_report["output_rows"]

    print("Cleaning 04_monthly_sip_inflows.csv ...")
    sip_df, sip_report = clean_monthly_sip_inflows()
    _write(sip_df, sip_report, "monthly_sip_inflows_clean.csv", "monthly_sip_inflows_clean_report.json")
    summary["monthly_sip_inflows"] = sip_report["output_rows"]

    print("Cleaning 05_category_inflows.csv ...")
    cat_df, cat_report = clean_category_inflows()
    _write(cat_df, cat_report, "category_inflows_clean.csv", "category_inflows_clean_report.json")
    summary["category_inflows"] = cat_report["output_rows"]

    print("Cleaning 06_industry_folio_count.csv ...")
    folio_df, folio_report = clean_industry_folio_count()
    _write(folio_df, folio_report, "industry_folio_count_clean.csv", "industry_folio_count_clean_report.json")
    summary["industry_folio_count"] = folio_report["output_rows"]

    print("Cleaning 09_portfolio_holdings.csv ...")
    hold_df, hold_report = clean_portfolio_holdings()
    _write(hold_df, hold_report, "portfolio_holdings_clean.csv", "portfolio_holdings_clean_report.json")
    summary["portfolio_holdings"] = hold_report["output_rows"]

    print("Cleaning 10_benchmark_indices.csv ...")
    bench_df, bench_report = clean_benchmark_indices()
    _write(bench_df, bench_report, "benchmark_indices_clean.csv", "benchmark_indices_clean_report.json")
    summary["benchmark_indices"] = bench_report["output_rows"]

    print("\nAll 10 datasets cleaned. Output row counts:")
    for name, count in summary.items():
        print(f"  {name:24s}: {count:>7,}")

    (PROCESSED_DIR / "_cleaning_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
