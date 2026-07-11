## Advanced_Analytics.ipynb — Error-fix plan

### Information gathered
- The notebook content was read successfully.
- It already contains computations for:
  - VaR/CVaR top funds (Insight 1)
  - Investor cohorts by total invested (Insight 2)
  - SIP continuity rate & at-risk investors (Insight 3)
  - Sector HHI concentration (Insight 4)
  - Recommender QA joining Sharpe picks with VaR/CVaR and HHI (Insight 5)
  - Rolling 90d Sharpe chart export to `Data/processed/rolling_sharpe_chart.png`.
- The previously failing tool call is due to missing `ripgrep` binary in the environment; this does not affect notebook correctness.

### Plan (code-level fixes)
1. **Ensure notebook is valid Python/Notebook JSON**
   - The file appears to be a plain text export of cell code rather than a proper `.ipynb` JSON structure.
   - Convert it to a real notebook (minimal structure) where each block becomes a code cell / markdown cell.
2. **Make execution deterministic & robust**
   - Add guards for missing columns in each loaded CSV (e.g., `var_95`, `cvar_95`, `at_risk`, `avg_gap_days`, `hhi_sector_concentration`, sharpe/risk columns).
   - Ensure numeric conversions are consistent (`amfi_code` Int64, returns numeric).
3. **Fix potential plotting / qcut edge cases**
   - Replace `pd.qcut(... q=min(5,len(qa)) ...)` with a safer fallback when `var_95` has too few unique values.
4. **Guarantee artifact path**
   - Ensure the chart is saved to `Data/processed/rolling_sharpe_chart.png` (already attempted), and close the figure after saving.

### Dependent files to edit
- `notebooks/Advanced_Analytics.ipynb` (primary)
- Potentially add `notebooks/requirements`/none (not expected)

### Followup steps
- Run the notebook via `jupyter nbconvert --execute` (or `python -m nbconvert` depending on your setup).
- Validate that `Data/processed/rolling_sharpe_chart.png` exists.

<ask_followup_question>
Proceed to convert/fix `notebooks/Advanced_Analytics.ipynb` into a proper executable Jupyter notebook JSON (and add robustness guards) as per the plan?
</ask_followup_question>

