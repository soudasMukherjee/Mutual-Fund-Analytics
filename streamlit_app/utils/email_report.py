"""
Automated weekly performance-summary email report.

Two responsibilities:
  1. ``build_weekly_report_html(...)`` — assemble a self-contained HTML email
     (all styling inline, no external CSS/JS/images) summarising the past
     week: headline KPIs, top/bottom fund performers by 1-week NAV change,
     SIP-inflow trend, and AUM-by-fund-house movement.
  2. ``send_email(...)`` — send that HTML via SMTP (SSL or STARTTLS), so this
     can run unattended on a schedule (cron / Windows Task Scheduler /
     GitHub Actions) — see ``scripts/weekly_email_report.py`` at the repo root.

Kept dependency-free beyond the standard library (``smtplib``, ``email``) so
sending doesn't require any extra package on top of what's already installed
for the dashboard.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

# ---------------------------------------------------------------------------
# Brand palette (mirrors utils/theme.py — kept independent so this module has
# no Streamlit dependency and can run standalone via cron)
# ---------------------------------------------------------------------------
PRIMARY = "#0B3D91"
SECONDARY = "#00B4D8"
ACCENT = "#FFB703"
POSITIVE = "#2E7D32"
NEGATIVE = "#C62828"
TEXT_DARK = "#0B1F3A"
MUTED = "#6B7A99"
BG = "#F5F8FC"


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    use_ssl: bool = True          # True -> SMTPS (e.g. port 465); False -> STARTTLS (e.g. port 587)
    sender_name: str = "Bluestock MF Analytics"


def _pct_color(value: float) -> str:
    return POSITIVE if value >= 0 else NEGATIVE


def _fmt_pct(value: float) -> str:
    return f"{value:+.2f}%"


def _rows_html(df: pd.DataFrame, cols: list[str], pct_cols: list[str]) -> str:
    rows = []
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            val = r[c]
            if c in pct_cols:
                color = _pct_color(val)
                cells.append(f'<td style="padding:8px 12px;color:{color};font-weight:600;">{_fmt_pct(val)}</td>')
            else:
                cells.append(f'<td style="padding:8px 12px;color:{TEXT_DARK};">{val}</td>')
        rows.append(f'<tr style="border-bottom:1px solid #E7ECF4;">{"".join(cells)}</tr>')
    return "\n".join(rows)


def compute_weekly_movers(nav_long: pd.DataFrame, top_n: int = 5, lookback_days: int = 5) -> pd.DataFrame:
    """N-trading-day NAV % change per scheme, from the daily NAV history.
    ``lookback_days`` is the number of trading days back to compare against
    (5 = 1 trading week, the default weekly-report window).
    """
    df = nav_long.sort_values(["scheme_name", "date"]).copy()
    span = lookback_days + 1

    def _pct_change(group: pd.DataFrame) -> float:
        group = group.sort_values("date")
        if len(group) < span:
            return float("nan")
        return (group["nav"].iloc[-1] / group["nav"].iloc[-span] - 1) * 100

    movers = df.groupby("scheme_name").apply(_pct_change, include_groups=False)
    movers = movers.rename("week_change_pct").reset_index().dropna()
    return movers.sort_values("week_change_pct", ascending=False)


def build_weekly_report_html(
    fund_scorecard: pd.DataFrame,
    nav_long: pd.DataFrame,
    sip_inflows: pd.DataFrame,
    aum_by_house: pd.DataFrame,
    report_date: datetime | None = None,
    top_n: int = 5,
    lookback_days: int = 5,
) -> str:
    report_date = report_date or datetime.now()

    movers = compute_weekly_movers(nav_long, top_n=top_n, lookback_days=lookback_days)
    top_gainers = movers.head(top_n)
    top_losers = movers.tail(top_n).sort_values("week_change_pct")

    latest_sip = sip_inflows.sort_values("month").iloc[-1]
    prev_sip = sip_inflows.sort_values("month").iloc[-2]
    sip_change = (latest_sip["sip_inflow_crore"] / prev_sip["sip_inflow_crore"] - 1) * 100

    latest_aum_date = aum_by_house["date"].max()
    aum_snapshot = aum_by_house[aum_by_house["date"] == latest_aum_date]
    total_aum_cr = aum_snapshot["aum_crore"].sum()

    top5_scored = fund_scorecard.sort_values("fund_score_0_100", ascending=False).head(top_n)

    gainers_html = _rows_html(top_gainers, ["scheme_name", "week_change_pct"], ["week_change_pct"])
    losers_html = _rows_html(top_losers, ["scheme_name", "week_change_pct"], ["week_change_pct"])
    scored_html = "\n".join(
        f'<tr style="border-bottom:1px solid #E7ECF4;">'
        f'<td style="padding:8px 12px;color:{TEXT_DARK};">{r.scheme_name}</td>'
        f'<td style="padding:8px 12px;color:{PRIMARY};font-weight:700;">{r.fund_score_0_100:.1f}</td>'
        f'</tr>'
        for r in top5_scored.itertuples()
    )

    html = f"""\
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Bluestock MF — Weekly Performance Summary</title></head>
<body style="margin:0;padding:0;background-color:{BG};font-family:Segoe UI,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:{BG};padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0"
             style="background-color:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 2px 10px rgba(11,61,145,0.08);">

        <tr><td style="background-color:{PRIMARY};padding:24px 32px;">
          <span style="color:#FFFFFF;font-size:1.4rem;font-weight:800;">🔷 Bluestock MF Analytics</span><br>
          <span style="color:#CFE0FF;font-size:0.9rem;">Weekly Performance Summary — {report_date:%d %b %Y}</span>
        </td></tr>

        <tr><td style="padding:28px 32px 8px 32px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td width="33%" style="padding:10px;text-align:center;background-color:{BG};border-radius:10px;">
                <div style="color:{MUTED};font-size:0.78rem;text-transform:uppercase;font-weight:700;">Total AUM</div>
                <div style="color:{TEXT_DARK};font-size:1.3rem;font-weight:800;">₹{total_aum_cr/100000:,.2f}L Cr</div>
              </td>
              <td width="4"></td>
              <td width="33%" style="padding:10px;text-align:center;background-color:{BG};border-radius:10px;">
                <div style="color:{MUTED};font-size:0.78rem;text-transform:uppercase;font-weight:700;">SIP Inflow ({latest_sip['month']})</div>
                <div style="color:{TEXT_DARK};font-size:1.3rem;font-weight:800;">₹{latest_sip['sip_inflow_crore']:,.0f} Cr</div>
                <div style="color:{_pct_color(sip_change)};font-size:0.8rem;font-weight:700;">{_fmt_pct(sip_change)} MoM</div>
              </td>
              <td width="4"></td>
              <td width="33%" style="padding:10px;text-align:center;background-color:{BG};border-radius:10px;">
                <div style="color:{MUTED};font-size:0.78rem;text-transform:uppercase;font-weight:700;">Active SIP Accounts</div>
                <div style="color:{TEXT_DARK};font-size:1.3rem;font-weight:800;">{latest_sip['active_sip_accounts_crore']:.2f} Cr</div>
              </td>
            </tr>
          </table>
        </td></tr>

        <tr><td style="padding:20px 32px 4px 32px;">
          <h3 style="color:{PRIMARY};margin:0 0 8px 0;">📈 Top {top_n} Gainers This Week</h3>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:0.88rem;">
            {gainers_html}
          </table>
        </td></tr>

        <tr><td style="padding:20px 32px 4px 32px;">
          <h3 style="color:{PRIMARY};margin:0 0 8px 0;">📉 Top {top_n} Decliners This Week</h3>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:0.88rem;">
            {losers_html}
          </table>
        </td></tr>

        <tr><td style="padding:20px 32px 4px 32px;">
          <h3 style="color:{PRIMARY};margin:0 0 8px 0;">🏆 Top {top_n} Rated Funds (Scorecard)</h3>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:0.88rem;">
            {scored_html}
          </table>
        </td></tr>

        <tr><td style="padding:24px 32px;background-color:{BG};">
          <span style="color:{MUTED};font-size:0.75rem;">
            Auto-generated by the Bluestock MF Analytics pipeline. Figures are computed from the
            latest cleaned dataset as of {report_date:%d %b %Y}; not investment advice.
          </span>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
"""
    return html


def send_email(html_body: str, subject: str, recipients: list[str], config: SMTPConfig) -> None:
    """Send the HTML report via SMTP. Raises on failure so the caller
    (Streamlit UI or the cron script) can surface the error clearly.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{config.sender_name} <{config.username}>"
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(html_body, "html"))

    context = ssl.create_default_context()
    if config.use_ssl:
        with smtplib.SMTP_SSL(config.host, config.port, context=context) as server:
            server.login(config.username, config.password)
            server.sendmail(config.username, recipients, msg.as_string())
    else:
        with smtplib.SMTP(config.host, config.port) as server:
            server.starttls(context=context)
            server.login(config.username, config.password)
            server.sendmail(config.username, recipients, msg.as_string())
