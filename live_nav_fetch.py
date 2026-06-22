import pandas as pd
import requests


AMFI_NAV_URL = "https://www.amfiindia.com/spages/NAVAll.txt?t="


def fetch_nav_text(url: str = AMFI_NAV_URL, timeout: int = 30) -> str:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.text


def parse_nav_text(text: str) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    current_section = None
    current_fund_house = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if ";" not in line:
            if "Mutual Fund" in line:
                current_fund_house = line
            else:
                current_section = line
            continue

        parts = [part.strip() for part in line.split(";")]
        if len(parts) < 3:
            continue

        record = {
            "section": current_section,
            "fund_house": current_fund_house,
            "scheme_name": parts[0],
            "nav": pd.to_numeric(parts[1], errors="coerce"),
            "nav_date": pd.to_datetime(parts[2], errors="coerce", dayfirst=True),
            "raw_line": line,
        }

        for index, value in enumerate(parts[3:], start=4):
            record[f"field_{index}"] = value

        records.append(record)

    return pd.DataFrame(records)


def fetch_live_nav() -> pd.DataFrame:
    return parse_nav_text(fetch_nav_text())


if __name__ == "__main__":
    nav_frame = fetch_live_nav()
    print(nav_frame.head())
