from pathlib import Path
import pandas as pd
import requests


MFAPI_URL_TEMPLATE = "https://api.mfapi.in/mf/{scheme_code}"
DEFAULT_SCHEME_CODE = 125497


def fetch_scheme_nav_json(scheme_code: int, timeout: int = 30) -> dict:
    url = MFAPI_URL_TEMPLATE.format(scheme_code=scheme_code)
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def parse_scheme_nav_response(payload: dict, scheme_code: int) -> pd.DataFrame:
    meta = payload.get("meta", {}) or {}
    nav_rows = payload.get("data", []) or []
    frame = pd.DataFrame(nav_rows)

    if frame.empty:
        frame = pd.DataFrame(columns=["date", "nav"])

    frame["date"] = pd.to_datetime(frame["date"], format="%d-%m-%Y", errors="coerce")
    frame["nav"] = pd.to_numeric(frame["nav"], errors="coerce")
    frame["scheme_code"] = meta.get("scheme_code", scheme_code)
    frame["scheme_name"] = meta.get("scheme_name")
    frame["fund_house"] = meta.get("fund_house")
    frame["scheme_type"] = meta.get("scheme_type")
    frame["scheme_category"] = meta.get("scheme_category")
    frame["isin_growth"] = meta.get("isin_growth")
    frame["isin_div_reinvestment"] = meta.get("isin_div_reinvestment")
    frame["status"] = payload.get("status")

    columns = [
        "scheme_code",
        "scheme_name",
        "fund_house",
        "scheme_type",
        "scheme_category",
        "isin_growth",
        "isin_div_reinvestment",
        "status",
        "date",
        "nav",
    ]
    return frame[columns].sort_values("date").reset_index(drop=True)


def save_scheme_nav_csv(
    scheme_code: int = DEFAULT_SCHEME_CODE,
    output_dir: Path | None = None,
) -> Path:
    base_dir = output_dir or Path(__file__).resolve().parent / "Data" / "raw"
    base_dir.mkdir(parents=True, exist_ok=True)

    payload = fetch_scheme_nav_json(scheme_code)
    nav_frame = parse_scheme_nav_response(payload, scheme_code)

    output_path = base_dir / f"mfapi_{scheme_code}_nav_raw.csv"
    nav_frame.to_csv(output_path, index=False)
    return output_path


if __name__ == "__main__":
    saved_path = save_scheme_nav_csv()
    print(f"Saved raw NAV CSV to {saved_path}")
