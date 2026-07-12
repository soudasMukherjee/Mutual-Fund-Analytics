# Bluestock MF Analytics — Streamlit Dashboard

A **Streamlit alternative to the Power BI dashboard brief**, built on the same cleaned
data pipeline (`Data/processed/*.csv` + the Day-2 SQLite star schema `bluestock_mf.db`).

## Why Streamlit instead of Power BI?

This was built by request as a full substitute — every chart, KPI, slicer, and the
drill-through interaction from the original Power BI spec is reproduced here, just
running in a browser via Python instead of the Power BI Desktop/Service stack.

**One thing that genuinely can't be replicated:** a `.pbix` file is a proprietary
binary format written by Power BI Desktop itself — there's no way to generate a valid
one outside that application. Since the ask was "do the Power BI tasks in Streamlit,"
the `.pbix` deliverable is replaced by the `streamlit_app/` folder itself (the
Streamlit equivalent of "the dashboard file"), plus `Dashboard.pdf` and the 4 page
PNGs, which **are** fully reproduced.

## Setup

```bash
cd "Mutual Fund Analytics"
pip install -r requirements.txt                    # existing project deps
pip install -r streamlit_app/requirements_streamlit.txt   # streamlit, plotly, Pillow
```

## Run the live dashboard

```bash
cd streamlit_app
streamlit run app.py
```

Opens at `http://localhost:8501`. Use the sidebar to move between pages:

| Page | File |
|---|---|
| Home (data connection status) | `app.py` |
| 1 · Industry Overview | `pages/1_Industry_Overview.py` |
| 2 · Fund Performance | `pages/2_Fund_Performance.py` |
| 3 · Investor Analytics | `pages/3_Investor_Analytics.py` |
| 4 · SIP & Market Trends | `pages/4_SIP_and_Market_Trends.py` |
| NAV Detail (drill-through target) | `pages/5_NAV_Detail.py` |
| 6 · Monte Carlo NAV Projection | `pages/6_Monte_Carlo_Projection.py` |
| 7 · Efficient Frontier (Markowitz) | `pages/7_Efficient_Frontier.py` |
| 8 · Automated Weekly Email Report | `pages/8_Automated_Email_Report.py` |

## Beyond the Power BI brief — bonus analytics pages

Three additional pages go past the original Power BI scope:

### Page 6 · Monte Carlo NAV Projection (5-year, uncertainty bands)
Simulates thousands of NAV paths using Geometric Brownian Motion calibrated on each fund's
own historical daily returns, and plots a fan chart with 5th/25th/50th/75th/95th percentile
bands out to a configurable horizon (default 5 years). See `utils/monte_carlo.py`.

### Page 7 · Efficient Frontier (Markowitz portfolio optimisation)
Pick any 3–10 funds and the page solves for the classical mean-variance efficient frontier:
Minimum-Volatility portfolio, Maximum-Sharpe ("tangency") portfolio, and the frontier curve
itself, via `scipy.optimize` (SLSQP), long-only and fully invested. Includes a random-portfolio
cloud for context and a correlation-matrix heatmap. See `utils/portfolio_optimizer.py`.

### Page 8 · Automated Weekly Email Report
Generates a self-contained HTML email (inline CSS, no external assets — safe for any email
client): headline KPIs, top/bottom weekly NAV movers, SIP-inflow trend, and top-rated funds
from the scorecard. Preview it live, send yourself a test copy via SMTP, or download the raw
`.html`. See `utils/email_report.py`.

For true unattended weekly sending (no one has to open the app), use the standalone script:

```bash
export BLUESTOCK_SMTP_HOST="smtp.gmail.com"
export BLUESTOCK_SMTP_PORT="465"
export BLUESTOCK_SMTP_USER="you@gmail.com"
export BLUESTOCK_SMTP_PASSWORD="your-app-password"

python scripts/weekly_email_report.py --to team@example.com          # sends
python scripts/weekly_email_report.py --to team@example.com --dry-run  # renders only, doesn't send
```

Schedule it with cron (`0 8 * * 1 ...` for every Monday 08:00), Windows Task Scheduler, or a
GitHub Actions `schedule:` workflow — see the in-app instructions on Page 8 for exact snippets.



```bash
cd streamlit_app
python export_report.py
```

Writes to `streamlit_app/exports/`:
- `page1_industry_overview.png`
- `page2_fund_performance.png`
- `page3_investor_analytics.png`
- `page4_sip_market_trends.png`
- `Dashboard.pdf` (all 4 pages combined)

This reuses the exact same data-loading functions as the live app, so figures always
match. It renders with matplotlib rather than Plotly/kaleido, specifically so it
doesn't require installing headless Chrome — it just works with what's already in
`requirements.txt`.

## What maps to what (Power BI brief → Streamlit)

| Power BI ask | Streamlit implementation |
|---|---|
| Connect to data, verify 8 tables, relationships | `app.py` — live connection-status panel querying `bluestock_mf.db` |
| KPI cards | `st.markdown` HTML cards, styled via `utils/theme.py` |
| Slicers | `st.sidebar.multiselect` per page |
| Scatter / bar / line / donut / heatmap | Plotly (`plotly.express` / `graph_objects`) — native hover tooltips on every chart |
| Sortable fund scorecard | `st.dataframe` with `column_config` (click any column header to sort) |
| Drill-through fund table → NAV detail | `st.session_state` + `st.switch_page()` |
| Bluestock colour theme & logo | `utils/theme.py` — deep-blue/cyan palette + CSS. **No official Bluestock logo/palette file exists in this repo**, so a fintech-appropriate blue/cyan scheme was used; drop a real logo at `streamlit_app/assets/bluestock_logo.png` and it'll appear in the sidebar automatically. |
| Export to PDF / PNG | `export_report.py` |
| Export to `.pbix` | Not reproducible outside Power BI Desktop (see above) — the `streamlit_app/` folder is the substitute deliverable. |

## Data source notes

- Connects to `bluestock_mf.db` (SQLite star schema: `dim_fund`, `dim_date`, `fact_nav`,
  `fact_transactions`, `fact_performance`, `fact_aum`, `fact_portfolio`,
  `fact_sip_industry`) as the primary source — this is the Streamlit equivalent of
  Power BI's SQLite ODBC connection.
- Falls back to the cleaned CSVs in `Data/processed/` automatically if the `.db` file
  isn't found, and always uses CSV for `category_inflows_clean.csv`,
  `industry_folio_count_clean.csv`, and `benchmark_indices_clean.csv` — these 3 were
  never loaded into the warehouse (they're industry-level series, not fund-grain data).
- KPI figures on Page 1 are computed live from the data. Monthly SIP inflow (₹31,002 Cr)
  and total folios (26.12 Cr) line up almost exactly with the brief's reference numbers.
  Total AUM (~₹62.7L Cr) and scheme count (1,522) reflect what's actually in this
  dataset rather than the brief's placeholder figures (₹81L Cr / 1,908 schemes) — real
  computed numbers were used throughout rather than hardcoding the brief's targets.

## Tested

- All 6 top-level scripts (`app.py` + 5 pages) run with zero exceptions in Streamlit
  "bare mode" (`python <page>.py`).
- Full server smoke-tested with `streamlit run app.py --server.headless true` —
  serves HTTP 200, no tracebacks in the server log.
- `export_report.py` runs clean end-to-end and produces all 5 output files.
