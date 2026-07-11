"""Recommender wrapper (deliverable name).

Supported input:
- risk_appetite: Low | Moderate | High

Output:
- prints top 3 funds by Sharpe ratio within matching risk_grade
- writes Data/processed/fund_recommendations_{risk_appetite}.csv

This is a thin wrapper around scripts/simple_fund_recommender.py.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Simple mutual fund recommender")
    parser.add_argument("--risk_appetite", required=True, help="Low | Moderate | High")
    args = parser.parse_args()

    # Import locally to keep script usable even if module path changes.
    from scripts.simple_fund_recommender import main as simple_main  # type: ignore

    # Delegate execution
    sys.argv = [sys.argv[0], f"--risk_appetite={args.risk_appetite}"]
    simple_main()


if __name__ == "__main__":
    main()

