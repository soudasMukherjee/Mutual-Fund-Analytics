## 10 key EDA findings

1. **Industry folio count grew steadily from Jan 2022 (~13.26 Cr) to Dec 2025 (~26.12 Cr), nearly doubling over the period.** (See: `notebooks/folio_count_growth_line_plotly.ipynb` — folio growth line chart)

2. **The chart shows milestone crossing events (15/20/25 Cr) occurring progressively, indicating sustained acquisition rather than a single spike.** (See: milestone markers on `notebooks/folio_count_growth_line_plotly.ipynb`)

3. **Despite growth, the month-to-month path is not strictly monotonic; the line reveals periods of slower advance between major thresholds.** (See: slope variations on `notebooks/folio_count_growth_line_plotly.ipynb`)

4. **Equity-focused folio totals (included in the dataset) represent the largest share of the overall folio count, supporting that most users are concentrated in equity schemes.** (See: `Data/processed/industry_folio_count_clean.csv` columns alongside `notebooks/folio_count_growth_line_plotly.ipynb`)

5. **Debt folios contribute a smaller, comparatively stable portion versus equity, suggesting steadier retention/rotation dynamics.** (See: `Data/processed/industry_folio_count_clean.csv` columns alongside `notebooks/folio_count_growth_line_plotly.ipynb`)

6. **Hybrid and “Others” categories fill the remaining share, showing that the industry folio base is diversified beyond equity.** (See: `Data/processed/industry_folio_count_clean.csv` columns alongside `notebooks/folio_count_growth_line_plotly.ipynb`)

7. **The endpoint labels (Jan 2022 and Dec 2025) confirm the absolute growth scale and provide an anchor for interpreting intermediate threshold dates.** (See: explicit endpoint annotations on `notebooks/folio_count_growth_line_plotly.ipynb`)

8. **Milestones are placed at the first month where the series reaches/exceeds each target (15/20/25 Cr), making the progression easy to communicate.** (See: auto-detected milestone logic in `notebooks/folio_count_growth_line_plotly.ipynb`)

9. **The dataset is monthly-granular (single value per month), so the chart reflects discrete sampling rather than daily volatility.** (See: `month` field usage in `notebooks/folio_count_growth_line_plotly.ipynb`)

10. **All folio values are stored in “crores” and the chart directly uses this unit, ensuring cross-checkability with printed milestone numbers.** (See: y-axis label + `total_folios_crore` usage in `notebooks/folio_count_growth_line_plotly.ipynb`)

