from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from utils.data_loader import (
    load_fund_scorecard, load_daily_returns_long, load_fact_sip_industry, load_fact_aum,
)
from utils.email_report import SMTPConfig, build_weekly_report_html, send_email
from utils.theme import register_plotly_template, inject_global_css, render_sidebar_brand, page_title

st.set_page_config(page_title="Automated Email Report — Bluestock MF", page_icon="📧", layout="wide")
register_plotly_template()
inject_global_css()
render_sidebar_brand()
page_title("📧", "Page 8 — Automated Weekly Email Report")

st.caption(
    "Generates a self-contained HTML email — top/bottom weekly movers, SIP inflow trend, "
    "AUM snapshot, top-rated funds — ready to send on a schedule. Preview it below, send "
    "yourself a test copy, or wire it up to run automatically every week (instructions at "
    "the bottom)."
)

fund_scorecard = load_fund_scorecard()
nav_long = load_daily_returns_long()
sip_inflows = load_fact_sip_industry()
if "year_month" in sip_inflows.columns and "month" not in sip_inflows.columns:
    sip_inflows = sip_inflows.rename(columns={"year_month": "month"})
aum_by_house = load_fact_aum()

top_n = st.sidebar.slider("Movers / top-funds shown", 3, 10, 5)

report_date = datetime.now()
html = build_weekly_report_html(
    fund_scorecard=fund_scorecard, nav_long=nav_long,
    sip_inflows=sip_inflows, aum_by_house=aum_by_house,
    report_date=report_date, top_n=top_n,
)

st.markdown("### 👁️ Live Preview")
with st.container(border=True):
    components.html(html, height=900, scrolling=True)

st.download_button(
    "⬇️ Download this report as .html", data=html,
    file_name=f"weekly_report_{report_date:%Y%m%d}.html", mime="text/html",
)

st.divider()

# ---------------------------------------------------------------------------
# Send now / test send
# ---------------------------------------------------------------------------
st.markdown("### ✉️ Send a Test Email")
st.caption(
    "Credentials are used only for this send and are never saved to disk. For real Gmail/"
    "Outlook accounts, use an **app password**, not your normal login password."
)

with st.form("send_email_form"):
    col1, col2 = st.columns(2)
    with col1:
        smtp_host = st.text_input("SMTP host", placeholder="smtp.gmail.com")
        smtp_user = st.text_input("SMTP username / sender email")
        smtp_pass = st.text_input("SMTP password / app password", type="password")
    with col2:
        smtp_port = st.number_input("SMTP port", value=465, step=1)
        use_ssl = st.selectbox("Connection type", ["SSL (port 465)", "STARTTLS (port 587)"]) == "SSL (port 465)"
        recipients_raw = st.text_input("Recipient email(s), comma-separated")

    submitted = st.form_submit_button("📨 Send report now", use_container_width=True)

if submitted:
    recipients = [r.strip() for r in recipients_raw.split(",") if r.strip()]
    if not (smtp_host and smtp_user and smtp_pass and recipients):
        st.error("Please fill in the SMTP host, username, password, and at least one recipient.")
    else:
        try:
            config = SMTPConfig(
                host=smtp_host, port=int(smtp_port), username=smtp_user,
                password=smtp_pass, use_ssl=use_ssl,
            )
            subject = f"Bluestock MF — Weekly Performance Summary ({report_date:%d %b %Y})"
            with st.spinner("Sending..."):
                send_email(html, subject, recipients, config)
            st.success(f"Sent to {', '.join(recipients)} ✅")
        except Exception as exc:  # noqa: BLE001
            st.error(f"Send failed: {exc}")

st.divider()

# ---------------------------------------------------------------------------
# Automation instructions
# ---------------------------------------------------------------------------
st.markdown("### ⏰ Automating This Weekly")
st.markdown(
    """
This page sends **on demand**. To have it actually fire every week without you opening the
app, use the standalone script `scripts/weekly_email_report.py` — same report, no Streamlit
needed — on a schedule:

**1. Set SMTP credentials as environment variables** (never hardcode them):
```bash
export BLUESTOCK_SMTP_HOST="smtp.gmail.com"
export BLUESTOCK_SMTP_PORT="465"
export BLUESTOCK_SMTP_USER="you@gmail.com"
export BLUESTOCK_SMTP_PASSWORD="your-app-password"
```

**2. Linux/macOS — cron** (every Monday 08:00):
```bash
0 8 * * 1 cd /path/to/Mutual_Fund_Analytics && python scripts/weekly_email_report.py --to team@example.com
```

**3. Windows — Task Scheduler**: weekly trigger running
`python scripts\\weekly_email_report.py --to team@example.com`, "Start in" set to the project folder.

**4. GitHub Actions** (cloud-hosted, no machine needs to stay on): add a workflow with a
`schedule: cron:` trigger, store the SMTP values as repo secrets, and run the same command.

Test it safely first with `--dry-run` — it renders the HTML to `streamlit_app/exports/` without
sending anything.
"""
)
