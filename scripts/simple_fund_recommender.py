from __future__ import annotations

"""Simple fund recommender.

User request:
- Input: risk appetite (Low / Moderate / High)
- Output: top 3 funds by Sharpe ratio within matching risk_grade
- Print recommendation table.

Inputs (Data/processed):
- sharpe_sortino_ranked_rf6_5.csv (preferred; contains sharpe_ratio + risk_grade)
- scheme_performance_clean.csv (fallback for sharpe_ratio + risk_grade)

Output:
- Data/processed/fund_recommendations_{risk_appetite_lower}.csv

Run:
- python scripts/simple_fund_recommender.py --risk_appetite High
"""

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"


RISK_MAP = {
    "low": ["Low"],
    "moderate": ["Moderate", "Medium"],
    "high": ["High"],
}


def _load_ranked() -> pd.DataFrame:
    ranked_path = PROCESSED_DIR / "sharpe_sortino_ranked_rf6_5.csv"
    if ranked_path.exists():
        return pd.read_csv(ranked_path)

    perf_path = PROCESSED_DIR / "scheme_performance_clean.csv"
    if not perf_path.exists():
        raise FileNotFoundError(
            "Missing both sharpe_sortino_ranked_rf6_5.csv and scheme_performance_clean.csv in Data/processed"
        )
    return pd.read_csv(perf_path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--risk_appetite", required=True, help="Low | Moderate | High")
    args = parser.parse_args()

    risk_appetite = str(args.risk_appetite).strip().lower()
    if risk_appetite not in RISK_MAP:
        raise ValueError("--risk_appetite must be one of: Low | Moderate | High")

    df = _load_ranked()

    # Normalize expected column names
    colmap = {c.lower(): c for c in df.columns}

    # Sharpe column (common variants)
    sharpe_col = None
    for cand in ["sharpe_ratio", "sharpe"]:
        if cand in colmap:
            sharpe_col = colmap[cand]
            break

    if sharpe_col is None:
        # try any column containing sharpe
        matches = [c for c in df.columns if "sharpe" in c.lower()]
        if matches:
            sharpe_col = matches[0]

    if sharpe_col is None:
        raise ValueError("Could not find sharpe ratio column in ranked/performance CSV")

    # risk_grade column (optional; dataset may not include it)
    risk_col = None
    for cand in ["risk_grade", "risk"]:
        if cand in colmap:
            risk_col = colmap[cand]
            break

    if risk_col is None:
        matches = [c for c in df.columns if "risk" in c.lower() and "grade" in c.lower()]
        if matches:
            risk_col = matches[0]

    # If the ranked CSV doesn't have risk_grade, attempt to map it from scheme_performance_clean.csv
    if risk_col is None:
        perf_path = PROCESSED_DIR / "scheme_performance_clean.csv"
        if perf_path.exists():
            perf_df = pd.read_csv(perf_path)
            perf_colmap = {c.lower(): c for c in perf_df.columns}
            for cand in ["risk_grade", "risk"]:
                if cand in perf_colmap:
                    risk_col = perf_colmap[cand]
                    df = df.merge(
                        perf_df[["amfi_code", risk_col]],
                        on="amfi_code",
                        how="left",
                        suffixes=("", "_perf"),
                    )
                    # after merge, risk_col may be duplicated; normalize to the merged one
                    if risk_col in df.columns:
                        break
            if risk_col is None:
                matches = [c for c in perf_df.columns if "risk" in c.lower() and "grade" in c.lower()]
                if matches:
                    risk_col = matches[0]
                    df = df.merge(
                        perf_df[["amfi_code", risk_col]],
                        on="amfi_code",
                        how="left",
                        suffixes=("", "_perf"),
                    )
        
    if risk_col is None:
        raise ValueError(
            "Could not find risk_grade (or risk) column in ranked/performance CSVs. "
            "Expected columns like risk_grade or risk in Data/processed/sharpe_sortino_ranked_rf6_5.csv or scheme_performance_clean.csv."
        )


    # Name column (optional)
    name_col = None
    for cand in ["scheme_name", "fund_name", "name"]:
        if cand in colmap:
            name_col = colmap[cand]
            break

    # Filter to matching risk_grade values
    allowed = set(RISK_MAP[risk_appetite])
    df[risk_col] = df[risk_col].astype(str).str.strip()

    filtered = df[df[risk_col].isin(allowed)].copy()
    if filtered.empty:
        raise ValueError(f"No funds found for risk appetite '{args.risk_appetite}'.")

    # Top 3 by Sharpe ratio
    filtered[sharpe_col] = pd.to_numeric(filtered[sharpe_col], errors="coerce")
    filtered = filtered.dropna(subset=[sharpe_col]).copy()

    top = filtered.sort_values(sharpe_col, ascending=False).head(3).copy()

    # Attach scheme_name if possible
    if name_col is None:
        # best-effort: attempt join from fund_master_clean
        fund_path = PROCESSED_DIR / "fund_master_clean.csv"
        if fund_path.exists() and "amfi_code" in top.columns:
            fund_df = pd.read_csv(fund_path)[["amfi_code", "scheme_name"]].drop_duplicates()
            top = top.merge(fund_df, on="amfi_code", how="left")
            name_col = "scheme_name" if "scheme_name" in top.columns else None

    rec = []
    for _, r in top.iterrows():
        rec.append(
            {
                "rank": len(rec) + 1,
                "scheme_name": r[name_col] if name_col and name_col in top.columns else None,
                "amfi_code": int(r["amfi_code"]) if "amfi_code" in top.columns and pd.notna(r["amfi_code"]) else None,
                "risk_grade": r[risk_col],
                "sharpe_ratio": float(r[sharpe_col]),
            }
        )

    rec_df = pd.DataFrame(rec)
    out_path = PROCESSED_DIR / f"fund_recommendations_{risk_appetite}.csv"
    rec_df.to_csv(out_path, index=False)

    print("Fund Recommendations")
    print("--------------------")
    print(rec_df.to_string(index=False))
    print(f"\nWrote: {out_path}")


if __name__ == "__main__":
    main()

