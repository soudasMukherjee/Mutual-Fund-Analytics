-- ============================================================================
-- Bluestock Fintech | Mutual Fund Analytics Capstone
-- Day 2: 10 Analytical SQL Queries
-- Database: bluestock_mf.db (SQLite)
-- ============================================================================
-- Run with:  sqlite3 bluestock_mf.db < sql/queries.sql
-- or load individually inside a notebook / DB browser.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- Q1. Top 5 funds by AUM (latest scheme-level AUM, from fact_performance)
-- ----------------------------------------------------------------------------
SELECT
    f.amfi_code,
    f.scheme_name,
    f.fund_house,
    p.aum_crore
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
ORDER BY p.aum_crore DESC
LIMIT 5;


-- ----------------------------------------------------------------------------
-- Q2. Average NAV per month (across all funds, then example for one scheme)
-- ----------------------------------------------------------------------------
-- 2a. Industry-wide average NAV by calendar month
SELECT
    d.year_month,
    ROUND(AVG(fn.nav), 4) AS avg_nav,
    COUNT(DISTINCT fn.amfi_code) AS funds_counted
FROM fact_nav fn
JOIN dim_date d ON d.date_id = fn.date_id
GROUP BY d.year_month
ORDER BY d.year_month;

-- 2b. Average NAV per month for a single scheme (SBI Bluechip Fund, 119551)
SELECT
    d.year_month,
    ROUND(AVG(fn.nav), 4) AS avg_nav
FROM fact_nav fn
JOIN dim_date d ON d.date_id = fn.date_id
WHERE fn.amfi_code = 119551
GROUP BY d.year_month
ORDER BY d.year_month;


-- ----------------------------------------------------------------------------
-- Q3. SIP inflow YoY growth (from fact_sip_industry, industry-level monthly data)
-- ----------------------------------------------------------------------------
SELECT
    year_month,
    sip_inflow_crore,
    yoy_growth_pct
FROM fact_sip_industry
ORDER BY year_month;

-- 3b. YoY growth computed directly from raw inflow (self-join on month-12 prior),
--     useful as a cross-check against the published yoy_growth_pct column.
SELECT
    curr.year_month,
    curr.sip_inflow_crore AS current_inflow_crore,
    prev.sip_inflow_crore AS year_ago_inflow_crore,
    ROUND(
        100.0 * (curr.sip_inflow_crore - prev.sip_inflow_crore) / prev.sip_inflow_crore,
        2
    ) AS computed_yoy_growth_pct
FROM fact_sip_industry curr
JOIN fact_sip_industry prev
    ON prev.year_month = strftime('%Y-%m', date(curr.year_month || '-01', '-1 year'))
ORDER BY curr.year_month;


-- ----------------------------------------------------------------------------
-- Q4. Transactions by state (total amount + count + average ticket size)
-- ----------------------------------------------------------------------------
SELECT
    state,
    COUNT(*) AS transaction_count,
    SUM(amount_inr) AS total_amount_inr,
    ROUND(AVG(amount_inr), 2) AS avg_amount_inr
FROM fact_transactions
GROUP BY state
ORDER BY total_amount_inr DESC;


-- ----------------------------------------------------------------------------
-- Q5. Funds with expense_ratio < 1%
-- ----------------------------------------------------------------------------
SELECT
    f.amfi_code,
    f.scheme_name,
    f.fund_house,
    f.plan,
    f.expense_ratio_pct
FROM dim_fund f
WHERE f.expense_ratio_pct < 1.0
ORDER BY f.expense_ratio_pct ASC;


-- ----------------------------------------------------------------------------
-- Q6. Top 10 funds by 3-year CAGR, with risk-adjusted context (Sharpe, Alpha)
-- ----------------------------------------------------------------------------
SELECT
    f.scheme_name,
    f.category,
    p.return_3yr_pct,
    p.sharpe_ratio,
    p.alpha,
    p.morningstar_rating
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
ORDER BY p.return_3yr_pct DESC
LIMIT 10;


-- ----------------------------------------------------------------------------
-- Q7. SIP vs Lumpsum vs Redemption split by city tier (T30 vs B30)
-- ----------------------------------------------------------------------------
SELECT
    city_tier,
    transaction_type,
    COUNT(*) AS transaction_count,
    SUM(amount_inr) AS total_amount_inr,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY city_tier), 2) AS pct_of_tier_transactions
FROM fact_transactions
GROUP BY city_tier, transaction_type
ORDER BY city_tier, total_amount_inr DESC;


-- ----------------------------------------------------------------------------
-- Q8. Average SIP amount by age group and gender (investor demographics)
-- ----------------------------------------------------------------------------
SELECT
    age_group,
    gender,
    COUNT(*) AS sip_count,
    ROUND(AVG(amount_inr), 2) AS avg_sip_amount_inr
FROM fact_transactions
WHERE transaction_type = 'SIP'
GROUP BY age_group, gender
ORDER BY age_group, gender;


-- ----------------------------------------------------------------------------
-- Q9. AUM growth by fund house: latest quarter vs. earliest quarter on record
-- ----------------------------------------------------------------------------
WITH bounds AS (
    SELECT fund_house,
           MIN(date_id) AS first_date_id,
           MAX(date_id) AS last_date_id
    FROM fact_aum
    GROUP BY fund_house
)
SELECT
    b.fund_house,
    first_a.aum_crore AS earliest_aum_crore,
    d_first.full_date AS earliest_date,
    last_a.aum_crore AS latest_aum_crore,
    d_last.full_date AS latest_date,
    ROUND(
        100.0 * (last_a.aum_crore - first_a.aum_crore) / first_a.aum_crore,
        2
    ) AS growth_pct
FROM bounds b
JOIN fact_aum first_a ON first_a.fund_house = b.fund_house AND first_a.date_id = b.first_date_id
JOIN fact_aum last_a  ON last_a.fund_house  = b.fund_house AND last_a.date_id  = b.last_date_id
JOIN dim_date d_first ON d_first.date_id = b.first_date_id
JOIN dim_date d_last  ON d_last.date_id  = b.last_date_id
ORDER BY growth_pct DESC;


-- ----------------------------------------------------------------------------
-- Q10. Sector concentration in equity fund portfolios (avg weight % by sector)
-- ----------------------------------------------------------------------------
SELECT
    fp.sector,
    COUNT(DISTINCT fp.amfi_code) AS funds_holding_sector,
    ROUND(AVG(fp.weight_pct), 2) AS avg_weight_pct,
    ROUND(SUM(fp.market_value_cr), 2) AS total_market_value_cr
FROM fact_portfolio fp
GROUP BY fp.sector
ORDER BY total_market_value_cr DESC;


-- ----------------------------------------------------------------------------
-- BONUS Q11. KYC verification rate and average annual income by payment mode
-- ----------------------------------------------------------------------------
SELECT
    payment_mode,
    COUNT(*) AS transaction_count,
    ROUND(100.0 * SUM(CASE WHEN kyc_status = 'Verified' THEN 1 ELSE 0 END) / COUNT(*), 2) AS kyc_verified_pct,
    ROUND(AVG(annual_income_lakh), 2) AS avg_annual_income_lakh
FROM fact_transactions
GROUP BY payment_mode
ORDER BY transaction_count DESC;


-- ----------------------------------------------------------------------------
-- BONUS Q12. Funds whose 1-year return beat their own 3-year benchmark CAGR
--            (simple momentum/outperformance screen)
-- ----------------------------------------------------------------------------
SELECT
    f.scheme_name,
    f.category,
    p.return_1yr_pct,
    p.benchmark_3yr_pct,
    ROUND(p.return_1yr_pct - p.benchmark_3yr_pct, 2) AS outperformance_pct
FROM fact_performance p
JOIN dim_fund f ON f.amfi_code = p.amfi_code
WHERE p.return_1yr_pct > p.benchmark_3yr_pct
ORDER BY outperformance_pct DESC;
