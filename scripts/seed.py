#!/usr/bin/env python3
"""
Quant Research Engine — Standalone Seed Script

Run this script to seed the PostgreSQL database with S&P 500 stock data.
Can be run independently or via the /api/seed endpoint.

Usage:
  python scripts/seed.py
  python scripts/seed.py --tickers AAPL MSFT NVDA
"""

import sys
import os
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.data.seed_database import fetch_and_seed_stocks, SP500_TOP_50


def main():
    parser = argparse.ArgumentParser(description="Seed the financial database")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Specific tickers to seed (default: top 50 S&P 500)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick seed with just 5 stocks for testing",
    )

    args = parser.parse_args()

    if args.quick:
        tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMD"]
        print(f"Quick seed: {tickers}")
    elif args.tickers:
        tickers = [t.upper() for t in args.tickers]
        print(f"Custom seed: {tickers}")
    else:
        tickers = SP500_TOP_50
        print(f"Full seed: {len(tickers)} tickers")

    fetch_and_seed_stocks(tickers)


if __name__ == "__main__":
    main()
