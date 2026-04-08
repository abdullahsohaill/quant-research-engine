"""
Quant Research Engine — Database Seeder

Fetches top 50 S&P 500 stocks from Wikipedia, pulls their financial data
from yfinance, and inserts into the PostgreSQL database.

Idempotent — safe to re-run. Uses upsert logic to avoid duplicates.
"""

import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

from backend.data.database import sync_engine, init_db_sync
from backend.data.models import Base, Stock, StockPrice, EarningsHistory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Top 50 S&P 500 tickers (curated list of most liquid) ─────
SP500_TOP_50 = [
    "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B",
    "UNH", "XOM", "JNJ", "JPM", "V", "PG", "MA", "HD", "CVX", "MRK",
    "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "WMT", "MCD", "CSCO",
    "TMO", "ACN", "ABT", "DHR", "NEE", "LIN", "TXN", "PM", "UNP",
    "RTX", "ORCL", "LOW", "AMGN", "COP", "AMD", "INTC", "QCOM",
    "BA", "GS", "MS", "SCHW", "BLK", "CRM",
]


def fetch_and_seed_stocks(tickers: list[str] = None):
    """
    Main seeding function. Fetches data for all tickers and inserts
    into database tables.
    """
    if tickers is None:
        tickers = SP500_TOP_50

    init_db_sync()
    logger.info(f"Starting database seed for {len(tickers)} tickers...")

    from sqlalchemy.orm import Session

    with Session(sync_engine) as session:
        for i, ticker in enumerate(tickers):
            try:
                logger.info(f"[{i+1}/{len(tickers)}] Fetching data for {ticker}...")
                _seed_single_stock(session, ticker)
                session.commit()
            except Exception as e:
                logger.error(f"Failed to seed {ticker}: {e}")
                session.rollback()
                continue

    logger.info("Database seeding complete!")


def _seed_single_stock(session, ticker: str):
    """Fetch and insert all data for a single stock."""
    stock = yf.Ticker(ticker)
    info = stock.info

    if not info or "symbol" not in info:
        logger.warning(f"No data found for {ticker}, skipping.")
        return

    # ── 1. Upsert Stock fundamentals ─────────────────────────
    stock_data = {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName", ticker),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange"),
        "country": info.get("country"),
        "website": info.get("website"),
        "description": (info.get("longBusinessSummary") or "")[:2000],
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "ps_ratio": info.get("priceToSalesTrailing12Months"),
        "peg_ratio": info.get("pegRatio"),
        "eps": info.get("trailingEps"),
        "forward_eps": info.get("forwardEps"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_day_avg": info.get("fiftyDayAverage"),
        "two_hundred_day_avg": info.get("twoHundredDayAverage"),
        "revenue": info.get("totalRevenue"),
        "revenue_growth": info.get("revenueGrowth"),
        "gross_margins": info.get("grossMargins"),
        "operating_margins": info.get("operatingMargins"),
        "profit_margins": info.get("profitMargins"),
        "ebitda": info.get("ebitda"),
        "total_debt": info.get("totalDebt"),
        "total_cash": info.get("totalCash"),
        "debt_to_equity": info.get("debtToEquity"),
        "return_on_equity": info.get("returnOnEquity"),
        "return_on_assets": info.get("returnOnAssets"),
        "free_cash_flow": info.get("freeCashflow"),
        "enterprise_value": info.get("enterpriseValue"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "updated_at": datetime.utcnow(),
    }

    stmt = insert(Stock).values(**stock_data)
    stmt = stmt.on_conflict_do_update(
        index_elements=["ticker"],
        set_={k: v for k, v in stock_data.items() if k != "ticker"},
    )
    session.execute(stmt)

    # ── 2. Fetch and insert historical prices (1 year) ────────
    hist = stock.history(period="1y")
    if not hist.empty:
        for date_idx, row in hist.iterrows():
            price_date = date_idx.date() if hasattr(date_idx, "date") else date_idx
            price_data = {
                "ticker": ticker,
                "date": price_date,
                "open": round(row.get("Open", 0), 4) if pd.notna(row.get("Open")) else None,
                "high": round(row.get("High", 0), 4) if pd.notna(row.get("High")) else None,
                "low": round(row.get("Low", 0), 4) if pd.notna(row.get("Low")) else None,
                "close": round(row.get("Close", 0), 4) if pd.notna(row.get("Close")) else None,
                "adj_close": round(row.get("Close", 0), 4) if pd.notna(row.get("Close")) else None,
                "volume": int(row.get("Volume", 0)) if pd.notna(row.get("Volume")) else None,
            }
            stmt = insert(StockPrice).values(**price_data)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_ticker_date",
                set_={k: v for k, v in price_data.items() if k not in ("ticker", "date")},
            )
            session.execute(stmt)

        logger.info(f"  → Inserted {len(hist)} price records for {ticker}")

    # ── 3. Fetch and insert earnings history ──────────────────
    try:
        earnings = stock.earnings_history
        if earnings is not None and not earnings.empty:
            for _, row in earnings.iterrows():
                earnings_date = row.get("Earnings Date")
                if earnings_date is None or pd.isna(earnings_date):
                    continue

                if hasattr(earnings_date, "date"):
                    earnings_date = earnings_date.date()

                earnings_data = {
                    "ticker": ticker,
                    "date": earnings_date,
                    "eps_actual": row.get("Reported EPS") if pd.notna(row.get("Reported EPS")) else None,
                    "eps_estimate": row.get("EPS Estimate") if pd.notna(row.get("EPS Estimate")) else None,
                    "eps_surprise": row.get("Surprise(%)") if pd.notna(row.get("Surprise(%)")) else None,
                }

                # Calculate surprise percentage
                if earnings_data["eps_actual"] and earnings_data["eps_estimate"]:
                    diff = earnings_data["eps_actual"] - earnings_data["eps_estimate"]
                    if earnings_data["eps_estimate"] != 0:
                        earnings_data["eps_surprise_pct"] = round(
                            (diff / abs(earnings_data["eps_estimate"])) * 100, 2
                        )

                stmt = insert(EarningsHistory).values(**earnings_data)
                stmt = stmt.on_conflict_do_update(
                    constraint="uq_earnings_ticker_date",
                    set_={k: v for k, v in earnings_data.items() if k not in ("ticker", "date")},
                )
                session.execute(stmt)

            logger.info(f"  → Inserted earnings data for {ticker}")
    except Exception as e:
        logger.warning(f"  → No earnings data for {ticker}: {e}")


if __name__ == "__main__":
    fetch_and_seed_stocks()
