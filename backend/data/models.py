"""
Quant Research Engine — Database Models

SQLAlchemy ORM models for storing financial data fetched from yfinance.
All tables are designed for analytical SQL queries by the AI orchestrator.
"""

from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    BigInteger,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class Stock(Base):
    """
    Core stock information — one row per ticker.
    Stores current snapshot of fundamentals and metadata.
    """

    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    sector = Column(String(100), nullable=True)
    industry = Column(String(255), nullable=True)
    market_cap = Column(BigInteger, nullable=True)
    currency = Column(String(10), default="USD")
    exchange = Column(String(50), nullable=True)
    country = Column(String(100), nullable=True)
    website = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    # ── Fundamentals (snapshot) ───────────────────────────────
    pe_ratio = Column(Float, nullable=True)
    forward_pe = Column(Float, nullable=True)
    pb_ratio = Column(Float, nullable=True)
    ps_ratio = Column(Float, nullable=True)
    peg_ratio = Column(Float, nullable=True)
    eps = Column(Float, nullable=True)
    forward_eps = Column(Float, nullable=True)
    dividend_yield = Column(Float, nullable=True)
    beta = Column(Float, nullable=True)
    fifty_two_week_high = Column(Float, nullable=True)
    fifty_two_week_low = Column(Float, nullable=True)
    fifty_day_avg = Column(Float, nullable=True)
    two_hundred_day_avg = Column(Float, nullable=True)

    # ── Financial Metrics ─────────────────────────────────────
    revenue = Column(BigInteger, nullable=True)
    revenue_growth = Column(Float, nullable=True)
    gross_margins = Column(Float, nullable=True)
    operating_margins = Column(Float, nullable=True)
    profit_margins = Column(Float, nullable=True)
    ebitda = Column(BigInteger, nullable=True)
    total_debt = Column(BigInteger, nullable=True)
    total_cash = Column(BigInteger, nullable=True)
    debt_to_equity = Column(Float, nullable=True)
    return_on_equity = Column(Float, nullable=True)
    return_on_assets = Column(Float, nullable=True)
    free_cash_flow = Column(BigInteger, nullable=True)
    enterprise_value = Column(BigInteger, nullable=True)
    ev_to_ebitda = Column(Float, nullable=True)

    # ── Metadata ──────────────────────────────────────────────
    updated_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Stock(ticker={self.ticker}, name={self.name})>"


class StockPrice(Base):
    """
    Historical daily price data — one row per ticker per date.
    Stores OHLCV data for time-series queries.
    """

    __tablename__ = "stock_prices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    open = Column(Float, nullable=True)
    high = Column(Float, nullable=True)
    low = Column(Float, nullable=True)
    close = Column(Float, nullable=True)
    adj_close = Column(Float, nullable=True)
    volume = Column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_ticker_date"),
        Index("ix_price_ticker_date", "ticker", "date"),
    )

    def __repr__(self):
        return f"<StockPrice(ticker={self.ticker}, date={self.date}, close={self.close})>"


class EarningsHistory(Base):
    """
    Quarterly earnings data — EPS actual vs estimate.
    Enables earnings surprise analysis.
    """

    __tablename__ = "earnings_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False)
    eps_actual = Column(Float, nullable=True)
    eps_estimate = Column(Float, nullable=True)
    eps_surprise = Column(Float, nullable=True)
    eps_surprise_pct = Column(Float, nullable=True)
    revenue_actual = Column(BigInteger, nullable=True)
    revenue_estimate = Column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_earnings_ticker_date"),
    )

    def __repr__(self):
        return f"<Earnings(ticker={self.ticker}, date={self.date}, eps={self.eps_actual})>"
