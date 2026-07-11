import pathlib


def test_processed_files_exist():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    data_processed = repo_root / "Data" / "processed"
    assert data_processed.exists(), f"Missing folder: {data_processed}"

    required = [
        "nav_history_clean.csv",
        "fund_master_clean.csv",
    ]
    for fn in required:
        p = data_processed / fn
        assert p.exists(), f"Missing processed file: {p}"
