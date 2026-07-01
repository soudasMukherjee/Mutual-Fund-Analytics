# Mutual Fund Analytics (Capstone)

## Table of Contents
- Project Overview
- Tech Stack (with logos)
- Dataset & Outputs (Data/)
- Project Structure
- Notebooks (what each one does + outputs)
- Scripts (what they do)
- Setup & Execution
- Reproducibility Notes

---

## Project Overview
This repository performs end-to-end analytics for mutual funds using cleaned datasets (NAV history, fund master, portfolio holdings, inflows/SIP, investor transactions, benchmarks, etc.). It then computes performance metrics such as:
- CAGR comparisons
- daily returns / rolling analytics
- Sharpe/Sortino (ranked views)
- tracking error vs benchmarks
- alpha/beta (OLS regression)
- maximum drawdown
- scorecards / fund quality summaries

The repo is organized as:
- **Data/raw/**: raw CSV extracts (and a PDF reference)
- **Data/processed/**: cleaned CSVs + JSON summaries + generated images
- **notebooks/**: analysis/visualization pipelines
- **scripts/**: batch utilities (cleaning, feature computation, database load)
- **sql/**: schema + query templates

---

## Tech Stack (with logos)
Below are the technologies used in this project. (Logos are represented as plain text placeholders to keep this README self-contained.)

- **Python**: 🐍 Python
- **Jupyter Notebook**: 📓 Jupyter
- **Pandas**: 📚 pandas
- **NumPy**: 🔢 NumPy
- **Matplotlib**: 📈 Matplotlib
- **Seaborn**: 🌊 Seaborn
- **Plotly**: ⚡ Plotly
- **Statsmodels**: 🧠 statsmodels (for OLS alpha/beta)
- **Scikit-learn (optional)**: 🤖 (if used in notebooks)
- **SQLite**: 🗄️ SQLite (via `bluestock_mf.db` / SQL folder)

> If you want *actual embedded logo images*, provide the image files (or allow remote URLs) and I’ll update the README with `<img>` tags.

---

## Dataset & Outputs
### Input Sources
- CSV extracts under `Data/raw/`
- Reference PDF: `Data/raw/Bluestock_MF_Capstone_Project.pdf`

### Processed Outputs
All computed/cleaned artifacts are written under:
- `Data/processed/*.csv`
- `Data/processed/*.json`
- `Data/processed/*.png`

Examples of processed outputs present in this repo:
- `nav_history_clean.csv`
- `daily_returns_all_schemes.csv`
- `scheme_performance_clean.csv`
- `alpha_beta.csv`
- `max_drawdown_by_fund.csv`
- `sharpe_ratio_ranked_rf6_5.csv`
- `sharpe_sortino_ranked_rf6_5.csv`
- `tracking_error_top5_funds_vs_benchmarks.csv`
- benchmark comparison images (e.g., Nifty50/Nifty100 top-5 comparison)

---

## Project Structure
- `data_ingestion.py` (root): data ingest / preparation entry point
- `live_nav_fetch.py` (root): optional live NAV fetch helper
- `temp_clean_investor_transactions_run.py` (root): helper for investor transaction cleaning runs
- `notebooks/`: interactive analysis + visualization
- `scripts/`:
  - `clean_all_datasets.py`
  - `clean_nav_history.py`
  - `compute_max_drawdown.py`
  - `load_to_sqlite.py`
- `sql/`:
  - `schema.sql`: SQLite schema
  - `queries.sql`: query templates

---

## Notebooks (purpose + outputs)

> Note: notebooks are executed in a typical flow. Exact cells can vary, but the intent and final artifacts are consistent.

### `notebooks/Performance_Analytics.ipynb`
**Purpose**: End-to-end performance analytics dashboard-style workflow.

**What it does (high-level):**
- Reads cleaned datasets from `Data/processed/`
- Computes/loads performance measures (returns, CAGR comparisons, risk stats)
- Generates figures/tables summarizing mutual fund performance across time horizons

**Outputs:**
- Intermediate/derived tables
- Plots that feed the report/scorecards
- May reuse artifacts such as `daily_returns_all_schemes.csv`, `alpha_beta.csv`, and ranking CSVs.

---

### `notebooks/fund_scorecard_0_100.ipynb`
**Purpose**: Generates a fund “scorecard” mapping performance/risk components into a 0–100 composite score.

**What it does:**
- Loads metric datasets (e.g., performance + risk rankings)
- Normalizes/weights metrics into a single score
- Produces summary tables to compare funds

**Outputs:**
- A scored fund table (often written to `Data/processed/fund_scorecard.csv`)
- Visualizations/tables used in the final narrative

---

### `notebooks/alpha_beta_run.ipynb`
**Purpose**: Computes alpha and beta of funds versus selected benchmarks using regression.

**What it does:**
- Loads `daily_returns_all_schemes.csv` and benchmark return series
- Runs an OLS regression per scheme
- Produces alpha/beta estimates

**Outputs:**
- `Data/processed/alpha_beta.csv`

---

### `notebooks/day_4_alpha_beta_ols_nifty100.ipynb`
**Purpose**: Alpha/beta computation specifically for a Nifty 100 benchmark universe.

**Outputs:**
- Alpha/beta dataset updates for that benchmark context

---

### `notebooks/day_4_compute_all_daily_returns_cagr_comparison.ipynb`
**Purpose**: Builds daily returns and the data needed for CAGR comparisons.

**Outputs:**
- `Data/processed/daily_returns_all_schemes.csv`
- CAGR comparison CSVs such as `Data/processed/cagr_comparison_1yr_3yr_5yr.csv`

---

### `notebooks/day_4_compute_cagr_and_comparison_table.ipynb`
**Purpose**: Generates CAGR summary tables for reporting.

**Outputs:**
- `Data/processed/cagr_comparison_1yr_3yr_5yr.csv`
- Additional comparison tables used downstream

---

### `notebooks/day_4_compute_daily_returns_and_validate.ipynb`
**Purpose**: Validates daily return calculations.

**Outputs:**
- Validation diagnostics (may not be written to disk)
- Ensures downstream metrics use reliable returns

---

### `notebooks/day_4_sharpe_sortino_ranked.ipynb`
**Purpose**: Computes Sharpe/Sortino ratios and produces ranked views.

**Outputs:**
- `Data/processed/sharpe_ratio_ranked_rf6_5.csv`
- `Data/processed/sharpe_sortino_ranked_rf6_5.csv`

---

### `notebooks/aum_growth_grouped_bar_seaborn.ipynb`
**Purpose**: Visualizes AUM growth trends by grouping.

**Outputs:**
- Charts generated using Seaborn

---

### `notebooks/category_inflow_heatmap_seaborn.ipynb`
**Purpose**: Visualizes category inflows as heatmaps.

**Outputs:**
- Seaborn heatmap figures
- Uses data from `Data/processed/category_inflows_clean.csv` and/or its summary JSON

---

### `notebooks/clean_investor_transactions.ipynb`
**Purpose**: Cleaning and preparation pipeline for investor transaction data.

**Outputs:**
- `Data/processed/investor_transactions_clean.csv`
- `Data/processed/investor_transactions_clean_report.json`

---

### `notebooks/clean_nav_history.ipynb`
**Purpose**: Cleaning pipeline for NAV history.

**Outputs:**
- `Data/processed/nav_history_clean.csv`
- `Data/processed/nav_history_clean_report.json`

---

### `notebooks/sip_inflow_monthly_plotly_alltime_high.ipynb`
**Purpose**: Monthly SIP inflow visualization, highlighting all-time highs.

**Outputs:**
- Plotly interactive charts
- Uses `Data/processed/monthly_sip_inflows_clean.csv`

---

### `notebooks/data_ingestion.py`
**Purpose**: In-repo helper for data ingestion/standardization.

**Outputs:**
- Raw-to-processed movement depending on notebook usage

---

### `notebooks/live_nav_fetch.py`
**Purpose**: Helper notebook for live NAV fetching.

**Outputs:**
- Updated NAV data used for further analytics (if executed)

---

### `notebooks/temp_clean_investor_transactions_run.py`
**Purpose**: Utility notebook/script for running investor transaction cleaning.

**Outputs:**
- Cleaning artifacts under `Data/processed/`

---

## Scripts (purpose)
- `scripts/clean_all_datasets.py`: batch cleaning for all datasets
- `scripts/clean_nav_history.py`: NAV cleaning pipeline
- `scripts/compute_max_drawdown.py`: computes max drawdown per fund
- `scripts/load_to_sqlite.py`: loads processed datasets into SQLite

---

## Setup & Execution
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. (Optional) Clean/prepare data using scripts:
   ```bash
   python scripts/clean_all_datasets.py
   python scripts/compute_max_drawdown.py
   ```
3. Run notebooks from `notebooks/` in VS Code / Jupyter.

---

## Reproducibility Notes
- If datasets in `Data/processed/` are already present, notebooks can run directly.
- Some notebooks may regenerate artifacts; use `Data/processed/` as the single source of derived outputs.
- Results depend on benchmark selection and date ranges.

