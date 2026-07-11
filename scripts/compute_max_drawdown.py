from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "Data" / "processed"

    nav_path = data_dir / "nav_history_clean.csv"
    fund_path = data_dir / "fund_master_clean.csv"

    out_path = data_dir / "max_drawdown_by_fund.csv"

    for p in [nav_path, fund_path]:
        if not p.exists():
            raise FileNotFoundError(f"Missing required file: {p}")

    nav_df = pd.read_csv(nav_path)
    fund_df = pd.read_csv(fund_path)

    required_nav_cols = {"amfi_code", "date", "nav"}
    missing_nav = required_nav_cols - set(nav_df.columns)
    if missing_nav:
        raise ValueError(f"nav_history_clean.csv missing columns: {sorted(missing_nav)}")

    required_fund_cols = {"amfi_code", "scheme_name"}
    missing_fund = required_fund_cols - set(fund_df.columns)
    if missing_fund:
        raise ValueError(f"fund_master_clean.csv missing columns: {sorted(missing_fund)}")

    nav_df["date"] = pd.to_datetime(nav_df["date"], errors="coerce")
    nav_df["amfi_code"] = pd.to_numeric(nav_df["amfi_code"], errors="coerce").astype("Int64")
    nav_df["nav"] = pd.to_numeric(nav_df["nav"], errors="coerce")

    nav_df = nav_df.dropna(subset=["date", "amfi_code", "nav"]).copy()
    nav_df = nav_df[nav_df["nav"] > 0].copy()  # running_max is meaningless with non-positive NAV

    fund_df["amfi_code"] = pd.to_numeric(fund_df["amfi_code"], errors="coerce").astype("Int64")
    fund_df = fund_df.dropna(subset=["amfi_code", "scheme_name"]).copy()

    name_map = (
        fund_df.drop_duplicates(subset=["amfi_code"]) 
        .set_index("amfi_code")["scheme_name"]
        .to_dict()
    )

    rows: list[dict[str, object]] = []

    for code, g in nav_df.groupby("amfi_code", sort=False):
        gg = g.sort_values("date")[["date", "nav"]].copy()
        if len(gg) < 2:
            continue

        running_max = gg["nav"].cummax()
        drawdown = gg["nav"] / running_max - 1.0  # min(NAV / running_max − 1)

        worst_dd = float(drawdown.min())
        worst_idx = drawdown.idxmin()
        worst_row = gg.loc[worst_idx]
        worst_ts = pd.to_datetime(worst_row["date"], errors="coerce")
        worst_date = worst_ts.date() if pd.notna(worst_ts) else None

        # Find peak date preceding/at worst trough.
        dd_to_worst = drawdown.loc[:worst_idx]
        peak_idx_candidates = (
            running_max.loc[:worst_idx] == running_max.loc[:worst_idx].max()
        )
        peak_idx = peak_idx_candidates[peak_idx_candidates].index.max()
        peak_ts = pd.to_datetime(gg.loc[peak_idx, "date"], errors="coerce")
        peak_date = peak_ts.date() if pd.notna(peak_ts) else None

        rows.append(
            {
                "amfi_code": int(code),
                "scheme_name": name_map.get(code, str(code)),
                "max_drawdown_pct": worst_dd * 100.0,
                "max_drawdown_start_date": str(peak_date),
                "max_drawdown_end_date": str(worst_date),
            }
        )

    out_df = pd.DataFrame(rows)
    out_df = out_df.sort_values(["max_drawdown_pct", "amfi_code"], ascending=[True, True])

    out_df.to_csv(out_path, index=False)

    print(f"Wrote: {out_path} ({len(out_df)} funds)")


if __name__ == "__main__":
    main()
