#!/usr/bin/env python
# coding: utf-8

# # Clean investor_transactions.csv
# 
# This notebook standardises and validates `Data/raw/08_investor_transactions.csv`, producing:
# - `Data/processed/investor_transactions_clean.csv`
# - `Data/processed/investor_transactions_clean_report.json`
# 
# Cleaning rules:
# - `transaction_type`: standardise to one of `SIP | Lumpsum | Redemption` (case/whitespace tolerant). Unknown values are kept as `Unknown`.
# - `amount_inr`: convert to numeric; keep only `amount_inr > 0`.
# - `transaction_date`: parse to datetime (`errors='coerce'`); drop rows with invalid dates.
# - `kyc_status`: normalise/validate to `Verified | Pending` (case/whitespace tolerant). Unknown values are kept as `Unknown`.

# In[1]:


from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


# In[6]:


RAW_PATH = Path('Data/raw/08_investor_transactions.csv').resolve()
PROCESSED_DIR = Path(__file__).resolve().parents[1] / 'Data' / 'processed'

OUT_CSV = PROCESSED_DIR / 'investor_transactions_clean.csv'
OUT_REPORT = PROCESSED_DIR / 'investor_transactions_clean_report.json'

RAW_PATH, OUT_CSV, OUT_REPORT


# In[3]:


def _norm_str_series(s: pd.Series) -> pd.Series:
    # Convert to string, trim, collapse inner whitespace, and uppercase
    return (
        s.astype('string')
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
        .str.upper()
    )


def clean_investor_transactions(raw_path: Path = RAW_PATH):
    df = pd.read_csv(raw_path)

    required = {'transaction_date', 'transaction_type', 'amount_inr', 'kyc_status'}
    missing_required = required - set(df.columns)
    if missing_required:
        raise ValueError(f'Missing required columns: {sorted(missing_required)}')

    report: dict[str, object] = {}
    before_rows = len(df)

    # transaction_type
    t = _norm_str_series(df['transaction_type'])
    mapping = {
        'SIP': 'SIP',
        'LUMPSUM': 'Lumpsum',
        'LUMP SUM': 'Lumpsum',
        'REDEMPTION': 'Redemption',
        'REDEMP': 'Redemption',
    }
    df['transaction_type'] = t.map(mapping).fillna('Unknown')

    # transaction_date
    df['transaction_date'] = pd.to_datetime(df['transaction_date'], errors='coerce')
    invalid_date_rows = int(df['transaction_date'].isna().sum())
    df = df.dropna(subset=['transaction_date']).copy()

    # amount_inr
    df['amount_inr'] = pd.to_numeric(df['amount_inr'], errors='coerce')
    invalid_amount_rows = int(df['amount_inr'].isna().sum())
    df = df.dropna(subset=['amount_inr']).copy()
    non_positive_amount_rows = int((df['amount_inr'] <= 0).sum())
    df = df[df['amount_inr'] > 0].copy()

    # kyc_status
    k = _norm_str_series(df['kyc_status'])
    k_map = {
        'VERIFIED': 'Verified',
        'PENDING': 'Pending',
    }
    df['kyc_status'] = k.map(k_map).fillna('Unknown')

    after_rows = len(df)

    # Light standardisation
    if 'investor_id' in df.columns:
        df['investor_id'] = df['investor_id'].astype('string').str.strip()
    if 'amfi_code' in df.columns:
        df['amfi_code'] = pd.to_numeric(df['amfi_code'], errors='coerce').astype('Int64')

    report.update({
        'input_path': str(raw_path),
        'before_rows': before_rows,
        'invalid_transaction_date_rows_dropped': invalid_date_rows,
        'invalid_amount_inr_rows_dropped': invalid_amount_rows,
        'non_positive_amount_inr_rows_removed': non_positive_amount_rows,
        'after_rows': after_rows,
        'transaction_type_value_counts': df['transaction_type'].value_counts(dropna=False).to_dict(),
        'kyc_status_value_counts': df['kyc_status'].value_counts(dropna=False).to_dict(),
    })

    # Stable ordering
    sort_cols = [c for c in ['investor_id', 'transaction_date', 'amfi_code'] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols).reset_index(drop=True)

    return df, report


# In[4]:


PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
cleaned_df, report = clean_investor_transactions(RAW_PATH)

cleaned_df.to_csv(OUT_CSV, index=False)
OUT_REPORT.write_text(json.dumps(report, indent=2), encoding='utf-8')

print('Wrote:', OUT_CSV)
print('Report:', OUT_REPORT)
print('\nSummary:', json.dumps(report, indent=2))



# In[ ]:




