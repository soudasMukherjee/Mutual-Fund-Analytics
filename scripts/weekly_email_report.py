"""
weekly_email_report.py — generate and send the weekly HTML performance
summary, meant to run unattended on a schedule.

Usage
-----
    python scripts/weekly_email_report.py --to alice@example.com bob@example.com

Reads SMTP credentials from environment variables (never hardcode secrets):
    BLUESTOCK_SMTP_HOST       e.g. smtp.gmail.com
    BLUESTOCK_SMTP_PORT       e.g. 465 (SSL) or 587 (STARTTLS)
    BLUESTOCK_SMTP_USER       sender email address
    BLUESTOCK_SMTP_PASSWORD   app password / SMTP password
    BLUESTOCK_SMTP_USE_SSL    "true" (default) or "false" -> STARTTLS

If ``--dry-run`` is passed (or no SMTP env vars are set), the report is only
rendered to ``streamlit_app/exports/weekly_report_<date>.html`` — nothing is
sent. This lets you preview the exact email before wiring up real credentials.

Scheduling
----------
Linux/macOS cron (every Monday at 08:00):
    0 8 * * 1 cd /path/to/Mutual_Fund_Analytics && \\
        /path/to/venv/bin/python scripts/weekly_email_report.py --to team@example.com

Windows Task Scheduler: create a weekly trigger that runs
    python.exe scripts\\weekly_email_report.py --to team@example.com
with "Start in" set to the project root.

GitHub Actions: add a workflow with a ``schedule: cron:`` trigger that
checks out the repo, installs requirements, sets the SMTP secrets as
repository secrets/env vars, and runs this script.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "streamlit_app"))

import pandas as pd  # noqa: E402

from utils.email_report import SMTPConfig, build_weekly_report_html, send_email  # noqa: E402

PROCESSED_DIR = REPO_ROOT / "Data" / "processed"
EXPORTS_DIR = REPO_ROOT / "streamlit_app" / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_inputs():
    fund_scorecard = pd.read_csv(PROCESSED_DIR / "fund_scorecard.csv")

    nav_long = pd.read_csv(PROCESSED_DIR / "daily_returns_all_schemes.csv")
    nav_long["date"] = pd.to_datetime(nav_long["date"])

    sip_inflows = pd.read_csv(PROCESSED_DIR / "monthly_sip_inflows_clean.csv")

    aum_by_house = pd.read_csv(PROCESSED_DIR / "aum_by_fund_house_clean.csv")
    aum_by_house["date"] = pd.to_datetime(aum_by_house["date"])

    return fund_scorecard, nav_long, sip_inflows, aum_by_house


def smtp_config_from_env() -> SMTPConfig | None:
    host = os.environ.get("BLUESTOCK_SMTP_HOST")
    user = os.environ.get("BLUESTOCK_SMTP_USER")
    password = os.environ.get("BLUESTOCK_SMTP_PASSWORD")
    if not (host and user and password):
        return None
    return SMTPConfig(
        host=host,
        port=int(os.environ.get("BLUESTOCK_SMTP_PORT", "465")),
        username=user,
        password=password,
        use_ssl=os.environ.get("BLUESTOCK_SMTP_USE_SSL", "true").lower() != "false",
    )


def main():
    parser = argparse.ArgumentParser(description="Generate + send the weekly Bluestock MF performance email.")
    parser.add_argument("--to", nargs="+", required=True, help="Recipient email address(es).")
    parser.add_argument("--dry-run", action="store_true", help="Render the HTML only; never send.")
    args = parser.parse_args()

    fund_scorecard, nav_long, sip_inflows, aum_by_house = load_inputs()
    report_date = datetime.now()

    html = build_weekly_report_html(
        fund_scorecard=fund_scorecard, nav_long=nav_long,
        sip_inflows=sip_inflows, aum_by_house=aum_by_house, report_date=report_date,
    )

    out_path = EXPORTS_DIR / f"weekly_report_{report_date:%Y%m%d}.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"Rendered report -> {out_path}")

    config = smtp_config_from_env()
    if args.dry_run or config is None:
        print("Dry run (or SMTP env vars not set) — email NOT sent. Preview the HTML file above.")
        return

    subject = f"Bluestock MF — Weekly Performance Summary ({report_date:%d %b %Y})"
    send_email(html, subject, args.to, config)
    print(f"Email sent to: {', '.join(args.to)}")


if __name__ == "__main__":
    main()
