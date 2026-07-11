# TODO

- [ ] Inspect existing SIP continuity logic script + outputs.
- [x] Inspect existing recommender/sector HHl/VaR/CVaR scripts.
- [ ] Create `scripts/recommender.py` wrapper (deliverable name) for simple fund recommender.
- [ ] Update `notebooks/Advanced_Analytics.ipynb`:
  - [ ] Add exactly 5 advanced insight markdown sections and supporting computation
    - [ ] Highest VaR/CVaR funds
    - [ ] Investor cohorts investing most
    - [ ] SIP continuity rate
    - [ ] Sector HHI concentration (compare equity funds)
    - [ ] Recommender validation vs risk & concentration
- [ ] Ensure `rolling_sharpe_chart.png` is generated and saved to `Data/processed/rolling_sharpe_chart.png`. (Day-5 notebook chart export)
- [ ] Run pipelines to confirm outputs exist.
  - [ ] python scripts/var_cvar_day5.py
  - [ ] python scripts/sector_hhi_concentration.py
  - [ ] python scripts/investor_cohort_analysis_first_tx_year.py
  - [ ] python scripts/sip_continuity_at_risk.py
- [ ] Execute notebooks:
  - [ ] notebooks/day_5_rolling_90d_sharpe_top5.ipynb (or regenerate chart inside Advanced_Analytics)
  - [ ] notebooks/Advanced_Analytics.ipynb

