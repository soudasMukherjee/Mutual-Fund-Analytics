"""
ETL: Daily NAV Refresh (mfapi.in) — all 40 schemes
====================================================
Fetches the latest NAV history for every scheme in ``fund_master_clean.csv``
from mfapi.in, merges it into ``Data/raw/02_nav_history.csv`` (the single
consolidated file the Day-2 cleaning pipeline expects), then re-runs
``clean_all_datasets.py`` so everything under ``Data/processed/`` is fresh.

Designed to be triggered by a scheduler (Windows Task Scheduler / cron) —
see ``scripts/run_nav_etl.bat`` and the setup instructions in
``scripts/README_scheduling.md``.

Run manually:
    python scripts/etl_fetch_nav_all.py

Exit codes:
    0 = success (all schemes fetched, or partial with warnings)
    1 = hard failure (couldn't read fund_master, or every scheme failed)
"""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "Data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "Data" / "processed"
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

NAV_HISTORY_RAW = RAW_DIR / "02_nav_history.csv"
FUND_MASTER = PROCESSED_DIR / "fund_master_clean.csv"
CLEAN_SCRIPT = PROJECT_ROOT / "scripts" / "clean_all_datasets.py"

MFAPI_URL_TEMPLATE = "https://api.mfapi.in/mf/{scheme_code}"
REQUEST_TIMEOUT_SECS = 30
RETRIES_PER_SCHEME = 3
RETRY_BACKOFF_SECS = 5
DELAY_BETWEEN_REQUESTS_SECS = 1.0  # be polite to the free public API

# ---------------------------------------------------------------------------
# Logging — one timestamped log file per run, plus console output
# ---------------------------------------------------------------------------
run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_path = LOG_DIR / f"nav_etl_{run_stamp}.log"

logger = logging.getLogger("nav_etl")
logger.setLevel(logging.INFO)
logger.handlers.clear()

_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

_fh = logging.FileHandler(log_path, encoding="utf-8")
_fh.setFormatter(_fmt)
logger.addHandler(_fh)

_ch = logging.StreamHandler(sys.stdout)
_ch.setFormatter(_fmt)
logger.addHandler(_ch)


# ---------------------------------------------------------------------------
# Fetch logic (per scheme)
# ---------------------------------------------------------------------------
def fetch_scheme_nav_json(scheme_code: int) -> dict:
    url = MFAPI_URL_TEMPLATE.format(scheme_code=scheme_code)
    last_exc: Exception | None = None

    for attempt in range(1, RETRIES_PER_SCHEME + 1):
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT_SECS)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001 - we want to retry on anything and log it
            last_exc = exc
            logger.warning(
                "Scheme %s: attempt %d/%d failed (%s)",
                scheme_code, attempt, RETRIES_PER_SCHEME, exc,
            )
            if attempt < RETRIES_PER_SCHEME:
                time.sleep(RETRY_BACKOFF_SECS * attempt)  # linear backoff

    raise RuntimeError(f"Scheme {scheme_code}: all {RETRIES_PER_SCHEME} attempts failed") from last_exc


def parse_scheme_nav_response(payload: dict, scheme_code: int) -> pd.DataFrame:
    """Return a DataFrame with just the columns the cleaning pipeline expects:
    amfi_code, date, nav.
    """
    nav_rows = payload.get("data", []) or []
    frame = pd.DataFrame(nav_rows)

    if frame.empty:
        return pd.DataFrame(columns=["amfi_code", "date", "nav"])

    frame["date"] = pd.to_datetime(frame["date"], format="%d-%m-%Y", errors="coerce")
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame["amfi_code"] = scheme_code

    frame = frame.dropna(subset=["date", "nav"])
    frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    return frame[["amfi_code", "date", "nav"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Merge into the consolidated raw file
# ---------------------------------------------------------------------------
def merge_into_nav_history(new_data: pd.DataFrame) -> tuple[int, int]:
    """Merge freshly-fetched NAV rows into Data/raw/02_nav_history.csv.
    Dedupes on (amfi_code, date), preferring the newly fetched value.
    Returns (rows_before, rows_after).
    """
    if NAV_HISTORY_RAW.exists():
        existing = pd.read_csv(NAV_HISTORY_RAW)
    else:
        existing = pd.DataFrame(columns=["amfi_code", "date", "nav"])

    rows_before = len(existing)

    combined = pd.concat([existing, new_data], ignore_index=True)
    # Keep the LAST occurrence per (amfi_code, date) => the freshly fetched row wins
    combined = combined.drop_duplicates(subset=["amfi_code", "date"], keep="last")
    combined = combined.sort_values(["amfi_code", "date"]).reset_index(drop=True)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(NAV_HISTORY_RAW, index=False)

    return rows_before, len(combined)


# ---------------------------------------------------------------------------
# Re-run the cleaning pipeline
# ---------------------------------------------------------------------------
def run_cleaning_pipeline() -> bool:
    logger.info("Re-running cleaning pipeline: %s", CLEAN_SCRIPT)
    result = subprocess.run(
        [sys.executable, str(CLEAN_SCRIPT)],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.stdout:
        logger.info("clean_all_datasets.py stdout:\n%s", result.stdout.strip())
    if result.returncode != 0:
        logger.error("clean_all_datasets.py FAILED (exit %d):\n%s", result.returncode, result.stderr.strip())
        return False
    logger.info("Cleaning pipeline completed successfully.")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    logger.info("=" * 70)
    logger.info("NAV ETL run started")

    if not FUND_MASTER.exists():
        logger.error("Cannot find %s — aborting.", FUND_MASTER)
        return 1

    fund_df = pd.read_csv(FUND_MASTER)
    scheme_codes = sorted(fund_df["amfi_code"].dropna().astype(int).unique().tolist())
    logger.info("Fetching NAV for %d schemes from mfapi.in ...", len(scheme_codes))

    all_frames: list[pd.DataFrame] = []
    succeeded, failed = [], []

    for i, code in enumerate(scheme_codes, start=1):
        try:
            payload = fetch_scheme_nav_json(code)
            frame = parse_scheme_nav_response(payload, code)
            if frame.empty:
                logger.warning("Scheme %s: fetched OK but returned 0 usable NAV rows.", code)
                failed.append(code)
            else:
                all_frames.append(frame)
                succeeded.append(code)
                logger.info("[%d/%d] Scheme %s: OK (%d NAV rows, latest=%s)",
                            i, len(scheme_codes), code, len(frame), frame["date"].max())
        except Exception as exc:  # noqa: BLE001
            logger.error("[%d/%d] Scheme %s: FAILED — %s", i, len(scheme_codes), code, exc)
            failed.append(code)

        time.sleep(DELAY_BETWEEN_REQUESTS_SECS)

    if not all_frames:
        logger.error("Every scheme failed to fetch. Aborting before touching any files.")
        return 1

    new_data = pd.concat(all_frames, ignore_index=True)
    rows_before, rows_after = merge_into_nav_history(new_data)
    logger.info(
        "Merged into %s: %d -> %d rows (%d new/updated).",
        NAV_HISTORY_RAW.name, rows_before, rows_after, rows_after - rows_before,
    )

    cleaning_ok = run_cleaning_pipeline()

    logger.info("Summary: %d/%d schemes succeeded. Failed codes: %s",
                len(succeeded), len(scheme_codes), failed if failed else "none")
    logger.info("Log file: %s", log_path)
    logger.info("NAV ETL run finished (cleaning_ok=%s)", cleaning_ok)
    logger.info("=" * 70)

    if failed and not succeeded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
