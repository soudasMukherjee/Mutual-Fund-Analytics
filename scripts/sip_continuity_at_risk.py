from __future__ import annotations

"""SIP continuity analysis.

Business rules (per capstone brief / user request):
- Consider investors with >= 6 SIP transactions.
- Compute the average gap (in days) between successive SIP transaction dates.
- Flag investors as "at-risk" if avg_gap_days > 35.

Inputs (Data/processed):
- investor_transactions_clean.csv

Output:
- Data/processed/sip_continuity_at_risk.csv

Run:
- python scripts/sip_continuity_at_risk.py
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"


def main() -> None:
    tx_path = PROCESSED_DIR / "investor_transactions_clean.csv"
    out_path = PROCESSED_DIR / "sip_continuity_at_risk.csv"

    if not tx_path.exists():
        raise FileNotFoundError(f"Missing input: {tx_path}")

    df = pd.read_csv(tx_path)

    if "investor_id" not in df.columns:
        raise ValueError("investor_transactions_clean.csv missing column: investor_id")
    if "transaction_date" not in df.columns:
        raise ValueError("investor_transactions_clean.csv missing column: transaction_date")
    if "transaction_type" not in df.columns:
        raise ValueError("investor_transactions_clean.csv missing column: transaction_type")

    df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    df = df.dropna(subset=["transaction_date"]).copy()

    # Filter to SIP only
    df["transaction_type"] = df["transaction_type"].astype(str)
    sip = df[df["transaction_type"].str.upper().str.strip().isin(["SIP"] )].copy()

    if sip.empty:
        raise ValueError("No SIP transactions found in investor_transactions_clean.csv (transaction_type == 'SIP').")

    # Sort and compute gaps per investor
    sip = sip.sort_values(["investor_id", "transaction_date"]).copy()

    grouped = sip.groupby("investor_id", sort=False)
    rows: list[dict] = []

    for inv_id, g in grouped:
        dates = g["transaction_date"].sort_values().to_list()
        if len(dates) < 6:
            continue

        # Day gaps between consecutive SIPs
        gaps = [
            (dates[i + 1] - dates[i]).days
            for i in range(len(dates) - 1)
        ]

        avg_gap_days = sum(gaps) / len(gaps) if gaps else None
        at_risk = bool(avg_gap_days is not None and avg_gap_days > 35)

        rows.append(
            {
                "investor_id": inv_id,
                "sip_tx_count": len(dates),
                "avg_gap_days": avg_gap_days,
                "at_risk": "at-risk" if at_risk else "ok",
                "max_gap_days": max(gaps) if gaps else None,
            }
        )

    out_df = pd.DataFrame(rows)
    out_df = out_df.sort_values(["at_risk", "avg_gap_days"], ascending=[False, False])

    out_df.to_csv(out_path, index=False)

    print(f"Wrote: {out_path} ({len(out_df)} investors)")


if __name__ == "__main__":
    main()

