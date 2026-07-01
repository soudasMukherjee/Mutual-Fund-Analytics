from pathlib import Path

import pandas as pd


DATASET_FILES = {
    "fund_master": "01_fund_master.csv",
    "nav_history": "02_nav_history.csv",
    "aum_by_fund_house": "03_aum_by_fund_house.csv",
    "monthly_sip_inflows": "04_monthly_sip_inflows.csv",
    "category_inflows": "05_category_inflows.csv",
    "industry_folio_count": "06_industry_folio_count.csv",
    "scheme_performance": "07_scheme_performance.csv",
    "investor_transactions": "08_investor_transactions.csv",
    "portfolio_holdings": "09_portfolio_holdings.csv",
    "benchmark_indices": "10_benchmark_indices.csv",
}


def load_all_datasets(data_dir: Path | None = None) -> dict[str, pd.DataFrame]:
    base_dir = data_dir or Path(__file__).resolve().parent / "Data" / "raw"
    datasets: dict[str, pd.DataFrame] = {}

    for dataset_name, filename in DATASET_FILES.items():
        datasets[dataset_name] = pd.read_csv(base_dir / filename)

    return datasets


def print_dataset_shapes(datasets: dict[str, pd.DataFrame]) -> None:
    for dataset_name, dataframe in datasets.items():
        print(f"{dataset_name}: {dataframe.shape}")


if __name__ == "__main__":
    loaded_datasets = load_all_datasets()
    print_dataset_shapes(loaded_datasets)
