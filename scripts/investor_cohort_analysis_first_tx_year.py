import json
from pathlib import Path

import pandas as pd


RAW_INPUT_CSV = Path("Data/processed/investor_transactions_clean.csv")
OUT_CSV = Path("Data/processed/investor_cohort_analysis_first_tx_year.csv")
OUT_JSON = Path("Data/processed/investor_cohort_analysis_first_tx_year.json")


def _safe_div(a, b):
    return a / b if b else 0.0


def compute_cohort_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Ensure datetime
    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date"])

    # cohort definition: first transaction year per investor
    first_tx = (
        df.sort_values(["investor_id", "transaction_date"])
        .groupby("investor_id", as_index=False)
        .first()
        [["investor_id", "transaction_date"]]
    )
    first_tx["first_tx_year"] = first_tx["transaction_date"].dt.year.astype(int)

    df = df.merge(first_tx[["investor_id", "first_tx_year"]], on="investor_id", how="inner")

    # Invested: count SIP/Lumpsum across entire history of investor in that cohort
    invested_mask = df["transaction_type"].isin(["SIP", "Lumpsum"])
    sip_mask = df["transaction_type"].eq("SIP")

    # avg SIP amount: average of individual SIP transaction amounts
    sip_tx = df[sip_mask].copy()

    # top fund preference: pick top amfi_code by (a) SIP tx count, (b) SIP amount
    sip_pref_count = (
        sip_tx.groupby(["first_tx_year", "amfi_code"], as_index=False)
        .size()
        .rename(columns={"size": "sip_tx_count"})
    )
    sip_pref_count["rank"] = sip_pref_count.groupby("first_tx_year")["sip_tx_count"].rank(
        method="first", ascending=False
    )
    top_by_count = sip_pref_count[sip_pref_count["rank"] == 1].drop(columns=["rank"])
    top_by_count = top_by_count.rename(columns={"amfi_code": "top_fund_by_sip_count_amfi_code"})


    sip_pref_amount = (
        sip_tx.groupby(["first_tx_year", "amfi_code"], as_index=False)["amount_inr"].sum()
        .rename(columns={"amount_inr": "sip_amount_sum_inr"})
    )
    sip_pref_amount["rank"] = sip_pref_amount.groupby("first_tx_year")["sip_amount_sum_inr"].rank(
        method="first", ascending=False
    )
    top_by_amount = sip_pref_amount[sip_pref_amount["rank"] == 1].drop(columns=["rank"])
    top_by_amount = top_by_amount.rename(
        columns={
            "amfi_code": "top_fund_by_sip_amount_amfi_code",
            "sip_amount_sum_inr": "top_fund_by_sip_amount_sum_inr",
        }
    )

    # cohort aggregates
    cohort_invested = (
        df[invested_mask]
        .groupby("first_tx_year", as_index=False)
        .agg(
            num_investors=("investor_id", "nunique"),
            total_invested_inr=("amount_inr", "sum"),
        )
    )

    cohort_avg_sip = (
        sip_tx.groupby("first_tx_year", as_index=False)
        .agg(avg_sip_amount_inr=("amount_inr", "mean"))
    )

    out = cohort_invested.merge(cohort_avg_sip, on="first_tx_year", how="left")
    out = out.merge(top_by_count[["first_tx_year", "top_fund_by_sip_count_amfi_code", "sip_tx_count"]], on="first_tx_year", how="left")
    out = out.merge(top_by_amount[["first_tx_year", "top_fund_by_sip_amount_amfi_code", "top_fund_by_sip_amount_sum_inr"]], on="first_tx_year", how="left")

    # Clean columns / ordering
    out = out.sort_values("first_tx_year").reset_index(drop=True)
    out.columns = [
        "first_tx_year",
        "num_investors",
        "total_invested_inr",
        "avg_sip_amount_inr",
        "top_fund_by_sip_count_amfi_code",
        "top_fund_by_sip_count_tx",
        "top_fund_by_sip_amount_amfi_code",
        "top_fund_by_sip_amount_sum_inr",
    ]

    # Harmonize missing values
    for c in [
        "avg_sip_amount_inr",
        "top_fund_by_sip_count_amfi_code",
        "top_fund_by_sip_count_tx",
        "top_fund_by_sip_amount_amfi_code",
        "top_fund_by_sip_amount_sum_inr",
    ]:
        if c in out.columns:
            out[c] = out[c].where(~out[c].isna(), None)

    return out


def main():
    if not RAW_INPUT_CSV.exists():
        raise FileNotFoundError(f"Missing input: {RAW_INPUT_CSV.resolve()}")

    df = pd.read_csv(RAW_INPUT_CSV)

    required_cols = {"investor_id", "transaction_date", "transaction_type", "amount_inr", "amfi_code"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in input CSV: {sorted(missing)}")

    out = compute_cohort_metrics(df)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT_CSV, index=False)

    meta = {
        "input_csv": str(RAW_INPUT_CSV),
        "output_csv": str(OUT_CSV),
        "output_json": str(OUT_JSON),
        "definitions": {
            "cohort": "Group investors by year of their first transaction_date (earliest transaction per investor_id).",
            "avg_sip_amount_inr": "Mean amount_inr across all SIP transactions (transaction_type == 'SIP') made by investors in that cohort (transaction-level mean).",
            "total_invested_inr": "Sum of amount_inr for transactions with transaction_type in ['SIP','Lumpsum'] across all investor history within each cohort.",
            "top fund preference": "Two metrics computed from SIP transactions within the cohort: (1) most preferred by SIP count (amfi_code with max SIP tx count), (2) most preferred by SIP invested amount (amfi_code with max sum(amount_inr) for SIP).",
        },
        "shape": {"rows": int(out.shape[0]), "columns": int(out.shape[1])},
        "preview": out.head(10).to_dict(orient="records"),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"Wrote: {OUT_CSV}")
    print(f"Wrote: {OUT_JSON}")


if __name__ == "__main__":
    main()

