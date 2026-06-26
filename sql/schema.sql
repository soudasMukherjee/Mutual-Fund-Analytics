-- ============================================================================
-- Bluestock Fintech | Mutual Fund Analytics Capstone
-- Day 2: SQLite Star Schema
-- ============================================================================
-- Design notes:
--   * dim_fund and dim_date are the two dimension tables.
--   * fact_nav, fact_transactions, fact_performance, fact_aum are the four
--     core fact tables requested for Day 2.
--   * fact_portfolio and fact_sip_industry are bonus fact tables added so
--     that all 10 cleaned source CSVs are represented in the warehouse
--     (per the project brief's own 8-table reference architecture).
--   * fact_aum and fact_sip_industry are *not* tied to a single amfi_code,
--     so they reference fund_house/date directly rather than dim_fund.
--   * All foreign keys to dim_date use the surrogate date_id (YYYYMMDD as
--     INTEGER) for fast range scans and to avoid string-date join costs.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- DIMENSION: dim_fund
-- One row per AMFI scheme. Source: 01_fund_master.csv
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_fund;
CREATE TABLE dim_fund (
    amfi_code           INTEGER PRIMARY KEY,
    fund_house          TEXT NOT NULL,
    scheme_name         TEXT NOT NULL,
    category            TEXT,
    sub_category        TEXT,
    plan                TEXT,
    launch_date         TEXT,
    benchmark           TEXT,
    expense_ratio_pct   REAL,
    exit_load_pct       REAL,
    min_sip_amount      REAL,
    min_lumpsum_amount  REAL,
    fund_manager        TEXT,
    risk_category       TEXT,
    sebi_category_code  TEXT
);

-- ----------------------------------------------------------------------------
-- DIMENSION: dim_date
-- One row per calendar day spanning the full NAV history range.
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS dim_date;
CREATE TABLE dim_date (
    date_id     INTEGER PRIMARY KEY,   -- YYYYMMDD, e.g. 20220103
    full_date   TEXT NOT NULL UNIQUE,  -- 'YYYY-MM-DD'
    year        INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    month       INTEGER NOT NULL,
    month_name  TEXT NOT NULL,
    year_month  TEXT NOT NULL,         -- 'YYYY-MM' convenience key
    day         INTEGER NOT NULL,
    day_of_week TEXT NOT NULL,
    is_weekday  INTEGER NOT NULL       -- 1 = Mon-Fri, 0 = Sat/Sun
);

-- ----------------------------------------------------------------------------
-- FACT: fact_nav
-- Daily NAV per scheme (forward-filled for non-trading days).
-- Source: nav_history_clean.csv (~64K rows after calendar-day fill)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_nav;
CREATE TABLE fact_nav (
    nav_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code       INTEGER NOT NULL,
    date_id         INTEGER NOT NULL,
    nav             REAL NOT NULL,
    daily_return_pct REAL,             -- populated post-load via window calc
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_id)   REFERENCES dim_date(date_id),
    UNIQUE (amfi_code, date_id)
);
CREATE INDEX idx_fact_nav_amfi_date ON fact_nav(amfi_code, date_id);
CREATE INDEX idx_fact_nav_date ON fact_nav(date_id);

-- ----------------------------------------------------------------------------
-- FACT: fact_transactions
-- Investor-level SIP / Lumpsum / Redemption transactions.
-- Source: investor_transactions_clean.csv (~32.8K rows)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_transactions;
CREATE TABLE fact_transactions (
    tx_id               INTEGER PRIMARY KEY AUTOINCREMENT,
    investor_id         TEXT NOT NULL,
    date_id             INTEGER NOT NULL,
    amfi_code           INTEGER NOT NULL,
    transaction_type    TEXT NOT NULL,   -- SIP | Lumpsum | Redemption | Unknown
    amount_inr          REAL NOT NULL,
    state               TEXT,
    city                TEXT,
    city_tier           TEXT,            -- T30 | B30
    age_group           TEXT,
    gender              TEXT,
    annual_income_lakh  REAL,
    payment_mode        TEXT,
    kyc_status          TEXT,            -- Verified | Pending | Unknown
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_id)   REFERENCES dim_date(date_id)
);
CREATE INDEX idx_fact_tx_amfi ON fact_transactions(amfi_code);
CREATE INDEX idx_fact_tx_date ON fact_transactions(date_id);
CREATE INDEX idx_fact_tx_state ON fact_transactions(state);
CREATE INDEX idx_fact_tx_investor ON fact_transactions(investor_id);

-- ----------------------------------------------------------------------------
-- FACT: fact_performance
-- One snapshot row per scheme of trailing return/risk metrics.
-- Source: scheme_performance_clean.csv (40 rows, as_of project data date)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_performance;
CREATE TABLE fact_performance (
    perf_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code           INTEGER NOT NULL,
    return_1yr_pct      REAL,
    return_3yr_pct      REAL,
    return_5yr_pct      REAL,
    benchmark_3yr_pct   REAL,
    alpha               REAL,
    beta                REAL,
    sharpe_ratio        REAL,
    sortino_ratio       REAL,
    std_dev_ann_pct     REAL,
    max_drawdown_pct    REAL,
    aum_crore           REAL,
    expense_ratio_pct   REAL,
    morningstar_rating  INTEGER,
    risk_grade          TEXT,
    data_quality_flag   TEXT,            -- anomaly notes from cleaning step
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    UNIQUE (amfi_code)
);
CREATE INDEX idx_fact_perf_amfi ON fact_performance(amfi_code);

-- ----------------------------------------------------------------------------
-- FACT: fact_aum
-- Quarterly AUM by fund house (industry-level, not scheme-level).
-- Source: aum_by_fund_house_clean.csv (90 rows)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_aum;
CREATE TABLE fact_aum (
    aum_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date_id         INTEGER NOT NULL,
    fund_house      TEXT NOT NULL,
    aum_lakh_crore  REAL,
    aum_crore       REAL,
    num_schemes     INTEGER,
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    UNIQUE (date_id, fund_house)
);
CREATE INDEX idx_fact_aum_date ON fact_aum(date_id);
CREATE INDEX idx_fact_aum_house ON fact_aum(fund_house);

-- ----------------------------------------------------------------------------
-- FACT (bonus): fact_portfolio
-- Top equity holdings per scheme as of Dec 2025.
-- Source: portfolio_holdings_clean.csv (322 rows)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_portfolio;
CREATE TABLE fact_portfolio (
    holding_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    amfi_code            INTEGER NOT NULL,
    date_id              INTEGER NOT NULL,
    stock_symbol          TEXT,
    stock_name            TEXT,
    sector                TEXT,
    weight_pct            REAL,
    market_value_cr       REAL,
    current_price_inr     REAL,
    FOREIGN KEY (amfi_code) REFERENCES dim_fund(amfi_code),
    FOREIGN KEY (date_id)   REFERENCES dim_date(date_id)
);
CREATE INDEX idx_fact_portfolio_amfi ON fact_portfolio(amfi_code);
CREATE INDEX idx_fact_portfolio_sector ON fact_portfolio(sector);

-- ----------------------------------------------------------------------------
-- FACT (bonus): fact_sip_industry
-- Industry-wide monthly SIP inflow metrics (not scheme-level).
-- Source: monthly_sip_inflows_clean.csv (48 rows)
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS fact_sip_industry;
CREATE TABLE fact_sip_industry (
    sip_id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    year_month                  TEXT NOT NULL UNIQUE,  -- 'YYYY-MM'
    sip_inflow_crore            REAL,
    active_sip_accounts_crore   REAL,
    new_sip_accounts_lakh       REAL,
    sip_aum_lakh_crore          REAL,
    yoy_growth_pct              REAL
);
CREATE INDEX idx_fact_sip_year_month ON fact_sip_industry(year_month);
