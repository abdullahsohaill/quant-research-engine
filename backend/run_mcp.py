"""
Quant Research Engine — MCP Server Runner

Entrypoint for running MCP servers as separate processes within Docker.
Accepts a --server argument to specify which server to run.

Usage:
  python -m backend.run_mcp --server financial --port 8001
  python -m backend.run_mcp --server postgres --port 8002
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Run MCP Server")
    parser.add_argument(
        "--server",
        choices=["financial", "postgres", "email"],
        required=True,
        help="Which MCP server to run",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port to listen on",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to",
    )

    args = parser.parse_args()

    if args.server == "financial":
        from backend.mcp_servers.financial_data_mcp import mcp

        print(f"Starting Financial Data MCP Server on {args.host}:{args.port}")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)

    elif args.server == "postgres":
        from backend.mcp_servers.postgres_mcp import mcp

        print(f"Starting PostgreSQL MCP Server on {args.host}:{args.port}")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)

    elif args.server == "email":
        from backend.mcp_servers.email_mcp import mcp

        print(f"Starting Email MCP Server on {args.host}:{args.port}")
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
