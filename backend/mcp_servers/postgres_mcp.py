"""
Quant Research Engine — PostgreSQL MCP Server

A standalone MCP server that exposes read-only SQL query execution
against the financial database. Includes built-in SQL injection prevention.

Tools exposed:
  - execute_read_only_sql: Executes SELECT queries against the database
  - get_table_schema: Returns schema info for available tables
  - get_sample_data: Returns sample rows from a table

Security:
  - Only SELECT statements are allowed
  - DROP, DELETE, UPDATE, INSERT, ALTER, TRUNCATE, CREATE are blocked
  - Query length is limited to prevent abuse

Run standalone:
  python -m backend.mcp_servers.postgres_mcp
  OR
  fastmcp run backend/mcp_servers/postgres_mcp.py:mcp --transport http --port 8002
"""

import json
import logging
import os
import re
from typing import Optional

from fastmcp import FastMCP
from sqlalchemy import create_engine, text, inspect

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Create MCP Server ─────────────────────────────────────────
mcp = FastMCP(
    "PostgreSQL Analytics Server",
    description="Executes read-only SQL queries against the financial database. "
    "Contains stock prices, fundamentals, and earnings data for S&P 500 companies. "
    "Tables: stocks, stock_prices, earnings_history.",
)

# ── Database Connection ───────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL_SYNC",
    os.getenv(
        "DATABASE_URL",
        "postgresql://quant_user:quant_password@localhost:5432/quant_research",
    ),
)
# Ensure we use psycopg2 driver for sync connection
if "asyncpg" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg", "postgresql")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5)


# ── SQL Safety Guards ─────────────────────────────────────────
BLOCKED_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "COPY", "LOAD", "pg_", "VACUUM", "REINDEX", "CLUSTER",
    ";--", "/*", "*/", "xp_", "sp_",
]

MAX_QUERY_LENGTH = 2000
MAX_ROWS = 100


def validate_sql_query(query: str) -> tuple[bool, str]:
    """
    Validate that a SQL query is safe to execute.

    Returns (is_safe, error_message).
    Blocks any non-SELECT queries and dangerous patterns.
    """
    if not query or not query.strip():
        return False, "Query cannot be empty."

    if len(query) > MAX_QUERY_LENGTH:
        return False, f"Query exceeds maximum length of {MAX_QUERY_LENGTH} characters."

    # Normalize whitespace and check for SELECT
    normalized = " ".join(query.upper().split())

    # Must start with SELECT or WITH (for CTEs)
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        return False, "Only SELECT queries are allowed. Query must start with SELECT or WITH."

    # Check for blocked keywords
    for keyword in BLOCKED_KEYWORDS:
        # Use word boundary matching to avoid false positives
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, normalized):
            return False, (
                f"Blocked keyword '{keyword}' detected. "
                f"Only read-only SELECT queries are permitted."
            )

    # Check for multiple statements (semicolons followed by more SQL)
    # Allow trailing semicolons but block chained statements
    stripped = query.strip().rstrip(";")
    if ";" in stripped:
        return False, "Multiple SQL statements are not allowed."

    return True, ""


@mcp.tool()
def execute_read_only_sql(query: str) -> str:
    """
    Execute a read-only SQL SELECT query against the financial database.

    Available tables:
    - stocks: Company info and fundamentals (ticker, name, sector, industry,
      market_cap, pe_ratio, eps, revenue, profit_margins, debt_to_equity, etc.)
    - stock_prices: Daily OHLCV price data (ticker, date, open, high, low,
      close, adj_close, volume)
    - earnings_history: Quarterly earnings (ticker, date, eps_actual,
      eps_estimate, eps_surprise, eps_surprise_pct)

    IMPORTANT: Only SELECT queries are allowed. All other operations are blocked
    for security.

    Args:
        query: A valid SQL SELECT query

    Returns:
        JSON string with query results as a list of row dictionaries,
        or an error message if the query is invalid
    """
    # ── Validate query safety ─────────────────────────────────
    is_safe, error_msg = validate_sql_query(query)
    if not is_safe:
        logger.warning(f"BLOCKED SQL query: {query[:100]}... Reason: {error_msg}")
        return json.dumps({
            "error": error_msg,
            "query_blocked": True,
            "hint": "Only SELECT queries against the stocks, stock_prices, and "
                    "earnings_history tables are allowed.",
        })

    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())
            rows = result.fetchmany(MAX_ROWS)

            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    # Handle special types for JSON serialization
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif isinstance(val, bytes):
                        val = val.decode("utf-8", errors="replace")
                    row_dict[col] = val
                data.append(row_dict)

            return json.dumps({
                "columns": columns,
                "data": data,
                "row_count": len(data),
                "truncated": len(rows) >= MAX_ROWS,
                "query_executed": query,
            }, indent=2, default=str)

    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        return json.dumps({
            "error": f"Query execution failed: {str(e)}",
            "query": query,
        })


@mcp.tool()
def get_table_schema() -> str:
    """
    Get the schema of all available tables in the database.

    Returns table names, column names, and column types to help you
    construct accurate SQL queries.

    Returns:
        JSON string with complete schema information for all tables
    """
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        schema = {}
        for table in tables:
            columns = inspector.get_columns(table)
            schema[table] = {
                "columns": [
                    {
                        "name": col["name"],
                        "type": str(col["type"]),
                        "nullable": col.get("nullable", True),
                    }
                    for col in columns
                ],
                "primary_key": [
                    pk["name"]
                    for pk in (inspector.get_pk_constraint(table).get("constrained_columns", []))
                ] if isinstance(inspector.get_pk_constraint(table).get("constrained_columns"), list) else [],
            }

        return json.dumps({
            "tables": schema,
            "available_tables": tables,
            "hint": "Use execute_read_only_sql to query these tables with SELECT statements.",
        }, indent=2)

    except Exception as e:
        logger.error(f"Error fetching schema: {e}")
        return json.dumps({"error": str(e)})


@mcp.tool()
def get_sample_data(table_name: str, limit: int = 5) -> str:
    """
    Get sample rows from a specific table to understand its data structure.

    Args:
        table_name: Name of the table (stocks, stock_prices, or earnings_history)
        limit: Number of sample rows to return (max 20)

    Returns:
        JSON string with sample data from the specified table
    """
    # Validate table name to prevent injection
    allowed_tables = ["stocks", "stock_prices", "earnings_history"]
    if table_name not in allowed_tables:
        return json.dumps({
            "error": f"Table '{table_name}' not found. Available tables: {allowed_tables}"
        })

    limit = min(max(1, limit), 20)

    try:
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        with engine.connect() as conn:
            result = conn.execute(text(query))
            columns = list(result.keys())
            rows = result.fetchall()

            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    val = row[i]
                    if hasattr(val, "isoformat"):
                        val = val.isoformat()
                    row_dict[col] = val
                data.append(row_dict)

            return json.dumps({
                "table": table_name,
                "columns": columns,
                "data": data,
                "row_count": len(data),
            }, indent=2, default=str)

    except Exception as e:
        logger.error(f"Error fetching sample data: {e}")
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8002
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
