"""
Quant Research Engine — Financial Data MCP Server

A standalone MCP server built with FastMCP that exposes financial data tools.
Uses yfinance for real-time and cached data retrieval.

Tools exposed:
  - get_stock_info: Current stock info and key fundamentals
  - get_stock_price_history: Historical OHLCV price data
  - get_fundamentals: Detailed fundamental analysis metrics
  - get_earnings_history: Quarterly earnings data with surprise analysis
  - compare_stocks: Side-by-side comparison of multiple tickers

Run standalone:
  python -m backend.mcp_servers.financial_data_mcp
  OR
  fastmcp run backend/mcp_servers/financial_data_mcp.py:mcp --transport http --port 8001
"""

import json
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
import yfinance as yf
from fastmcp import FastMCP
import uuid
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Create MCP Server ─────────────────────────────────────────
mcp = FastMCP(
    "Financial Data Server",
    description="Provides real-time and historical financial data via yfinance. "
    "Offers stock info, price history, fundamentals, earnings, and comparisons.",
)


def _safe_number(value) -> Optional[float]:
    """Safely convert a value to float, handling NaN/None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return round(float(value), 4)
    except (ValueError, TypeError):
        return None


def _safe_int(value) -> Optional[int]:
    """Safely convert a value to int, handling NaN/None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _format_large_number(value) -> str:
    """Format large numbers for readability (e.g., 1.5T, 200B)."""
    if value is None:
        return "N/A"
    abs_val = abs(value)
    if abs_val >= 1e12:
        return f"${value / 1e12:.2f}T"
    elif abs_val >= 1e9:
        return f"${value / 1e9:.2f}B"
    elif abs_val >= 1e6:
        return f"${value / 1e6:.2f}M"
    else:
        return f"${value:,.2f}"


@mcp.tool()
def get_stock_info(ticker: str) -> str:
    """
    Get current stock information and key metrics for a given ticker symbol.

    Returns company name, sector, current price, market cap, and key ratios.
    Use this as a first step when analyzing any stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'NVDA', 'MSFT')

    Returns:
        JSON string with stock information and key metrics
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        if not info or "symbol" not in info:
            return json.dumps({"error": f"No data found for ticker '{ticker}'"})

        result = {
            "ticker": ticker.upper(),
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "exchange": info.get("exchange", "N/A"),
            "currency": info.get("currency", "USD"),
            "current_price": _safe_number(info.get("currentPrice") or info.get("regularMarketPrice")),
            "previous_close": _safe_number(info.get("previousClose")),
            "market_cap": _safe_int(info.get("marketCap")),
            "market_cap_formatted": _format_large_number(info.get("marketCap")),
            "pe_ratio": _safe_number(info.get("trailingPE")),
            "forward_pe": _safe_number(info.get("forwardPE")),
            "eps": _safe_number(info.get("trailingEps")),
            "dividend_yield": _safe_number(info.get("dividendYield")),
            "beta": _safe_number(info.get("beta")),
            "52_week_high": _safe_number(info.get("fiftyTwoWeekHigh")),
            "52_week_low": _safe_number(info.get("fiftyTwoWeekLow")),
            "50_day_avg": _safe_number(info.get("fiftyDayAverage")),
            "200_day_avg": _safe_number(info.get("twoHundredDayAverage")),
            "volume": _safe_int(info.get("volume")),
            "avg_volume": _safe_int(info.get("averageVolume")),
            "description": (info.get("longBusinessSummary") or "")[:500],
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error fetching stock info for {ticker}: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_stock_price_history(
    ticker: str,
    period: str = "6mo",
) -> str:
    """
    Get historical OHLCV price data for a stock.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'NVDA')
        period: Time period - '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max'

    Returns:
        JSON string with date-indexed price data (open, high, low, close, volume)
    """
    try:
        stock = yf.Ticker(ticker.upper())
        hist = stock.history(period=period)

        if hist.empty:
            return json.dumps({"error": f"No price data for {ticker} over period {period}"})

        records = []
        for date_idx, row in hist.iterrows():
            records.append({
                "date": date_idx.strftime("%Y-%m-%d"),
                "open": _safe_number(row.get("Open")),
                "high": _safe_number(row.get("High")),
                "low": _safe_number(row.get("Low")),
                "close": _safe_number(row.get("Close")),
                "volume": _safe_int(row.get("Volume")),
            })

        # Also compute summary statistics
        closes = hist["Close"].dropna()
        summary = {
            "ticker": ticker.upper(),
            "period": period,
            "data_points": len(records),
            "latest_close": _safe_number(closes.iloc[-1]) if len(closes) > 0 else None,
            "period_high": _safe_number(closes.max()),
            "period_low": _safe_number(closes.min()),
            "period_return_pct": _safe_number(
                ((closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]) * 100
            ) if len(closes) > 1 else None,
            "avg_daily_volume": _safe_int(hist["Volume"].mean()),
            "volatility_pct": _safe_number(closes.pct_change().std() * (252 ** 0.5) * 100),
        }

        # Return only last 30 data points + summary to keep response manageable
        return json.dumps({
            "summary": summary,
            "recent_prices": records[-30:],
        }, indent=2)

    except Exception as e:
        logger.error(f"Error fetching price history for {ticker}: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_fundamentals(ticker: str) -> str:
    """
    Get detailed fundamental analysis metrics for a stock.

    Returns comprehensive financial data including valuation ratios,
    profitability metrics, balance sheet data, and growth indicators.
    Use this for deep-dive fundamental analysis.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'NVDA')

    Returns:
        JSON string with detailed fundamental metrics organized by category
    """
    try:
        stock = yf.Ticker(ticker.upper())
        info = stock.info

        if not info or "symbol" not in info:
            return json.dumps({"error": f"No fundamental data for {ticker}"})

        result = {
            "ticker": ticker.upper(),
            "name": info.get("longName", ticker),

            "valuation": {
                "market_cap": _safe_int(info.get("marketCap")),
                "market_cap_formatted": _format_large_number(info.get("marketCap")),
                "enterprise_value": _safe_int(info.get("enterpriseValue")),
                "enterprise_value_formatted": _format_large_number(info.get("enterpriseValue")),
                "trailing_pe": _safe_number(info.get("trailingPE")),
                "forward_pe": _safe_number(info.get("forwardPE")),
                "peg_ratio": _safe_number(info.get("pegRatio")),
                "price_to_book": _safe_number(info.get("priceToBook")),
                "price_to_sales": _safe_number(info.get("priceToSalesTrailing12Months")),
                "ev_to_ebitda": _safe_number(info.get("enterpriseToEbitda")),
                "ev_to_revenue": _safe_number(info.get("enterpriseToRevenue")),
            },

            "profitability": {
                "gross_margins": _safe_number(info.get("grossMargins")),
                "operating_margins": _safe_number(info.get("operatingMargins")),
                "profit_margins": _safe_number(info.get("profitMargins")),
                "return_on_equity": _safe_number(info.get("returnOnEquity")),
                "return_on_assets": _safe_number(info.get("returnOnAssets")),
            },

            "income_statement": {
                "revenue": _safe_int(info.get("totalRevenue")),
                "revenue_formatted": _format_large_number(info.get("totalRevenue")),
                "revenue_growth": _safe_number(info.get("revenueGrowth")),
                "ebitda": _safe_int(info.get("ebitda")),
                "ebitda_formatted": _format_large_number(info.get("ebitda")),
                "net_income": _safe_int(info.get("netIncomeToCommon")),
                "earnings_growth": _safe_number(info.get("earningsGrowth")),
                "eps_trailing": _safe_number(info.get("trailingEps")),
                "eps_forward": _safe_number(info.get("forwardEps")),
            },

            "balance_sheet": {
                "total_cash": _safe_int(info.get("totalCash")),
                "total_cash_formatted": _format_large_number(info.get("totalCash")),
                "total_debt": _safe_int(info.get("totalDebt")),
                "total_debt_formatted": _format_large_number(info.get("totalDebt")),
                "debt_to_equity": _safe_number(info.get("debtToEquity")),
                "current_ratio": _safe_number(info.get("currentRatio")),
                "book_value": _safe_number(info.get("bookValue")),
            },

            "cash_flow": {
                "free_cash_flow": _safe_int(info.get("freeCashflow")),
                "free_cash_flow_formatted": _format_large_number(info.get("freeCashflow")),
                "operating_cash_flow": _safe_int(info.get("operatingCashflow")),
            },

            "dividends": {
                "dividend_yield": _safe_number(info.get("dividendYield")),
                "dividend_rate": _safe_number(info.get("dividendRate")),
                "payout_ratio": _safe_number(info.get("payoutRatio")),
                "ex_dividend_date": str(info.get("exDividendDate", "N/A")),
            },

            "analyst_targets": {
                "target_high": _safe_number(info.get("targetHighPrice")),
                "target_low": _safe_number(info.get("targetLowPrice")),
                "target_mean": _safe_number(info.get("targetMeanPrice")),
                "target_median": _safe_number(info.get("targetMedianPrice")),
                "recommendation": info.get("recommendationKey", "N/A"),
                "num_analysts": _safe_int(info.get("numberOfAnalystOpinions")),
            },
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error fetching fundamentals for {ticker}: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_earnings_history(ticker: str) -> str:
    """
    Get quarterly earnings history with EPS estimates vs actuals.

    Shows earnings surprises and trends over recent quarters.
    Useful for analyzing earnings consistency and market expectations.

    Args:
        ticker: Stock ticker symbol (e.g., 'AAPL', 'NVDA')

    Returns:
        JSON string with quarterly earnings data and surprise percentages
    """
    try:
        stock = yf.Ticker(ticker.upper())

        # Try to get earnings history
        earnings_data = []

        try:
            earnings_hist = stock.earnings_history
            if earnings_hist is not None and not earnings_hist.empty:
                for _, row in earnings_hist.iterrows():
                    entry = {
                        "date": str(row.get("Earnings Date", "N/A")),
                        "eps_estimate": _safe_number(row.get("EPS Estimate")),
                        "eps_actual": _safe_number(row.get("Reported EPS")),
                        "surprise_pct": _safe_number(row.get("Surprise(%)")),
                    }
                    if entry["eps_actual"] is not None and entry["eps_estimate"] is not None:
                        entry["beat_estimate"] = entry["eps_actual"] > entry["eps_estimate"]
                    earnings_data.append(entry)
        except Exception:
            pass

        # Also get quarterly earnings if available
        quarterly_earnings = []
        try:
            qe = stock.quarterly_earnings
            if qe is not None and not qe.empty:
                for date_idx, row in qe.iterrows():
                    quarterly_earnings.append({
                        "quarter": str(date_idx),
                        "revenue": _safe_int(row.get("Revenue")),
                        "earnings": _safe_int(row.get("Earnings")),
                    })
        except Exception:
            pass

        result = {
            "ticker": ticker.upper(),
            "earnings_history": earnings_data,
            "quarterly_earnings": quarterly_earnings,
            "total_quarters_reported": len(earnings_data),
            "beat_rate_pct": (
                round(
                    sum(1 for e in earnings_data if e.get("beat_estimate")) / len(earnings_data) * 100, 1
                )
                if earnings_data
                else None
            ),
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        logger.error(f"Error fetching earnings for {ticker}: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool
def compare_stocks(tickers: str) -> str:
    """
    Compare multiple stocks side-by-side on key metrics.

    Generates a comparison table with valuation, profitability, and
    growth metrics for 2 or more stocks.

    Args:
        tickers: Comma-separated ticker symbols (e.g., 'NVDA,AMD' or 'AAPL,MSFT,GOOGL')

    Returns:
        JSON string with side-by-side comparison data
    """
    try:
        ticker_list = [t.strip().upper() for t in tickers.split(",")]
        if len(ticker_list) < 2:
            return json.dumps({"error": "Provide at least 2 tickers separated by commas"})

        comparisons = []
        for ticker in ticker_list:
            stock = yf.Ticker(ticker)
            info = stock.info

            if not info or "symbol" not in info:
                comparisons.append({"ticker": ticker, "error": "Data not available"})
                continue

            comparisons.append({
                "ticker": ticker,
                "name": info.get("longName", ticker),
                "sector": info.get("sector", "N/A"),
                "market_cap_formatted": _format_large_number(info.get("marketCap")),
                "current_price": _safe_number(
                    info.get("currentPrice") or info.get("regularMarketPrice")
                ),
                "pe_ratio": _safe_number(info.get("trailingPE")),
                "forward_pe": _safe_number(info.get("forwardPE")),
                "peg_ratio": _safe_number(info.get("pegRatio")),
                "eps": _safe_number(info.get("trailingEps")),
                "revenue_growth": _safe_number(info.get("revenueGrowth")),
                "profit_margins": _safe_number(info.get("profitMargins")),
                "operating_margins": _safe_number(info.get("operatingMargins")),
                "return_on_equity": _safe_number(info.get("returnOnEquity")),
                "debt_to_equity": _safe_number(info.get("debtToEquity")),
                "beta": _safe_number(info.get("beta")),
                "dividend_yield": _safe_number(info.get("dividendYield")),
                "recommendation": info.get("recommendationKey", "N/A"),
                "target_mean_price": _safe_number(info.get("targetMeanPrice")),
            })

        return json.dumps({
            "comparison": comparisons,
            "tickers_compared": ticker_list,
            "comparison_date": datetime.now().strftime("%Y-%m-%d"),
        }, indent=2)

    except Exception as e:
        logger.error(f"Error comparing stocks: {e}")
        return json.dumps({"error": str(e)})



@mcp.tool()
def generate_financial_chart(
    title: str,
    chart_type: str,
    x_labels: list[str],
    y_values: list[float],
    y_label: str = "Value"
) -> str:
    """
    Generate an interactive Plotly chart and save it as an HTML file.
    Always call this when you need to visualize quantitative financial data in your analysis.
    
    Args:
        title: The title of the chart
        chart_type: The type of chart ('line' or 'bar')
        x_labels: Array of labels for the X-axis (e.g. dates or categories)
        y_values: Array of numeric values for the Y-axis
        y_label: Label for the Y-axis
        
    Returns:
        JSON string containing the markdown link to embed the chart in the report.
    """
    try:
        import plotly.graph_objects as go
        
        fig = go.Figure()
        
        if chart_type.lower() == 'bar':
            fig.add_trace(go.Bar(x=x_labels, y=y_values, name=y_label, marker_color='#3b82f6'))
        else:
            fig.add_trace(go.Scatter(x=x_labels, y=y_values, mode='lines+markers', name=y_label, line=dict(color='#1e40af', width=3)))
            
        fig.update_layout(
            title=title,
            xaxis_title="Record" if not len(x_labels) else "",
            yaxis_title=y_label,
            template="plotly_white",
            margin=dict(l=40, r=40, t=60, b=40),
            hovermode="x unified"
        )
        
        chart_id = str(uuid.uuid4())[:8]
        filename = f"chart_{chart_id}.html"
        static_dir = os.path.join(os.path.dirname(__file__), "..", "static", "charts")
        os.makedirs(static_dir, exist_ok=True)
        filepath = os.path.join(static_dir, filename)
        
        # Save as interactive HTML
        fig.write_html(filepath, include_plotlyjs="cdn", full_html=False)
        
        # Return markdown to embed (as iframe or direct link, but markdown supports raw HTML or simple links)
        # We will return an iframe embed capability for the frontend, but standard markdown link as fallback.
        markdown_link = f"[Interactive Chart: {title}](/static/charts/{filename})"
        html_embed = f'<iframe src="/static/charts/{filename}" width="100%" height="400px" frameborder="0"></iframe>'
        
        return json.dumps({
            "success": True,
            "markdown": f"{markdown_link}\n\n{html_embed}"
        })
        
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8001
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
