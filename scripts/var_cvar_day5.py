from __future__ import annotations

"""Historical VaR(95%) and CVaR(95%) for all schemes (Day 5).

Definitions (per user request):
- VaR (95%) = 5th percentile of daily_return distribution
- CVaR (95%) = mean of returns below (or equal to) the VaR threshold

Inputs (Data/processed):
- daily_returns_all_schemes.csv with columns: date, amfi_code, scheme_name, daily_return

Output:
- Data/processed/var_cvar_report.csv

Run:
- python scripts/var_cvar_day5.py
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"


def main() -> None:
    in_path = PROCESSED_DIR / "daily_returns_all_schemes.csv"
    out_path = PROCESSED_DIR / "var_cvar_report.csv"

    if not in_path.exists():
        raise FileNotFoundError(f"Missing input: {in_path}")

    df = pd.read_csv(in_path)

    required = {"amfi_code", "scheme_name", "daily_return"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"daily_returns_all_schemes.csv missing columns: {sorted(missing)}")

    df["amfi_code"] = pd.to_numeric(df["amfi_code"], errors="coerce").astype("Int64")
    df["daily_return"] = pd.to_numeric(df["daily_return"], errors="coerce")
    df["scheme_name"] = df["scheme_name"].astype(str)

    df = df.dropna(subset=["amfi_code", "scheme_name", "daily_return"]).copy()

    # Compute historical VaR/CVaR per scheme.
    # VaR_95 = quantile at 0.05
    grouped = df.groupby(["amfi_code", "scheme_name"], sort=False)

    rows: list[dict] = []
    for (code, name), g in grouped:
        r = g["daily_return"].dropna().astype(float)
        if len(r) < 2:
            continue
        var_95 = float(r.quantile(0.05, interpolation="linear"))
        tail = r[r <= var_95]
        cvar_95 = float(tail.mean()) if len(tail) else var_95

        rows.append(
            {
                "amfi_code": int(code),
                "scheme_name": name,
                "var_95": var_95,
                "cvar_95": cvar_95,
                "n_obs": int(len(r)),
                "n_tail": int(len(tail)),
            }
        )

    out_df = pd.DataFrame(rows)
    if out_df.empty:
        raise RuntimeError("VaR/CVaR computation produced no rows")

    out_df = out_df.sort_values("var_95", ascending=True).reset_index(drop=True)
    out_df.to_csv(out_path, index=False)

    print(f"Wrote: {out_path} ({len(out_df)} schemes)")
    print(out_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()

