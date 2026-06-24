from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


RAW_NAV_HISTORY_PATH = Path(__file__).resolve().parent.parent / "Data" / "raw" / "02_nav_history.csv"
PROCESSED_DIR = Path(__file__).resolve().parent.parent / "Data" / "processed"

OUTPUT_CSV_PATH = PROCESSED_DIR / "nav_history_clean.csv"
OUTPUT_REPORT_PATH = PROCESSED_DIR / "nav_history_clean_report.json"


def _to_int_series(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def clean_nav_history(
    raw_path: Path = RAW_NAV_HISTORY_PATH,
) -> tuple[pd.DataFrame, dict]:
    df = pd.read_csv(raw_path)

    expected_cols = {"amfi_code", "date", "nav"}
    missing = expected_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {raw_path}: {sorted(missing)}")

    df = df[["amfi_code", "date", "nav"]].copy()

    report: dict[str, object] = {}

    # Parse types
    df["amfi_code"] = _to_int_series(df["amfi_code"])
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["nav"] = pd.to_numeric(df["nav"], errors="coerce")

    before_rows = len(df)

    invalid_date_rows = int(df["date"].isna().sum())
    df = df.dropna(subset=["amfi_code", "date"]).copy()

    invalid_nav_rows = int(df["nav"].isna().sum())
    # We keep rows with NaN nav only if date is valid; but for ffill we only want valid NAV anchors.
    # Drop NaN NAVs before dedupe/fill.
    df = df.dropna(subset=["nav"]).copy()

    after_type_rows = len(df)

    # Sort and dedupe by (amfi_code, date)
    df = df.sort_values(["amfi_code", "date", "nav"], kind="mergesort")

    # If multiple NAV values exist for same (amfi_code,date), keep the first after sorting.
    dup_subset = df.duplicated(subset=["amfi_code", "date"], keep="first")
    duplicate_date_rows = int(dup_subset.sum())
    df = df.loc[~dup_subset].copy()

    # Forward-fill missing NAV across all calendar days per amfi_code
    # Build complete date ranges per fund; concat for performance.
    df["amfi_code"] = df["amfi_code"].astype(int)

    filled_frames = []
    total_original_rows = len(df)
    total_filled_rows = 0

    for amfi_code, g in df.groupby("amfi_code", sort=False):
        g = g.sort_values("date")
        start = g["date"].min()
        end = g["date"].max()

        full_idx = pd.date_range(start=start, end=end, freq="D")
        g2 = (
            g.set_index("date")[["nav"]]
            .reindex(full_idx)
            .sort_index()
        )
        # Count fill candidates (missing nav that gets filled)
        missing_before = int(g2["nav"].isna().sum())

        g2["nav"] = g2["nav"].ffill()
        missing_after = int(g2["nav"].isna().sum())

        filled_now = missing_before - missing_after
        total_filled_rows += max(0, filled_now)

        g2 = g2.reset_index().rename(columns={"index": "date"})
        g2["amfi_code"] = amfi_code
        filled_frames.append(g2)

    out = pd.concat(filled_frames, ignore_index=True)

    # Final sort
    out = out.sort_values(["amfi_code", "date"], kind="mergesort").reset_index(drop=True)

    # Validate nav > 0
    non_positive_rows = int((out["nav"] <= 0).sum())
    out_valid = out.dropna(subset=["nav"]).copy()
    out_valid = out_valid[out_valid["nav"] > 0].copy()

    report.update(
        {
            "input_path": str(raw_path),
            "before_rows": before_rows,
            "invalid_date_rows_dropped": invalid_date_rows,
            "invalid_nav_rows_dropped": invalid_nav_rows,
            "after_type_rows": after_type_rows,
            "duplicate_rows_removed_by_(amfi_code,date)": duplicate_date_rows,
            "total_original_rows_used": total_original_rows,
            "total_filled_rows_forward_filled": total_filled_rows,
            "non_positive_nav_rows_removed": non_positive_rows,
            "output_rows": len(out_valid),
        }
    )

    return out_valid, report


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    cleaned_df, report = clean_nav_history(RAW_NAV_HISTORY_PATH)

    cleaned_df.to_csv(OUTPUT_CSV_PATH, index=False)
    OUTPUT_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote cleaned NAV history to: {OUTPUT_CSV_PATH}")
    print(f"Report: {OUTPUT_REPORT_PATH}")


if __name__ == "__main__":
    main()

