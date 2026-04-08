"""
Quant Research Engine — FastAPI Application

Main entry point for the backend API server. Exposes:
  - POST /api/analyze      — Submit a query for AI-powered financial analysis
  - POST /api/analyze/stream — SSE streaming endpoint for real-time progress
  - GET  /api/health        — Health check with service status
  - POST /api/seed          — Trigger database seeding

Architecture:
  FastAPI → Orchestrator Engine (native tool-calling loop)
    → MCP Client → Financial MCP Server (yfinance)
    → MCP Client → PostgreSQL MCP Server (SQL)
    → Gemini API (function calling + text generation)
"""

import json
import logging
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
import os

from backend.config import get_settings
from backend.schemas.api import (
    AnalyzeRequest,
    AnalyzeResponse,
    HealthResponse,
    SeedRequest,
    SeedResponse,
    AnalysisMetadata,
)
from backend.orchestrator.engine import AnalysisEngine, get_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
settings = get_settings()

# ── Global engine reference ───────────────────────────────────
engine: AnalysisEngine | None = None


# ══════════════════════════════════════════════════════════════
# APPLICATION LIFECYCLE
# ══════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    global engine

    logger.info("=" * 60)
    logger.info("Quant Research Engine — Starting up...")
    logger.info("=" * 60)

    # Initialize database tables
    try:
        from backend.data.database import init_db
        await init_db()
        logger.info("✓ Database initialized")
    except Exception as e:
        logger.warning(f"✗ Database initialization failed: {e}")

    # Auto-seed database (limit to top 5 for quick startup)
    try:
        from backend.data.seed_database import fetch_and_seed_stocks, SP500_TOP_50
        # Check if we should seed in background
        logger.info("Auto-seeding database top 5 stocks...")
        fetch_and_seed_stocks(SP500_TOP_50[:5])
    except Exception as e:
        logger.warning(f"Auto-seed skipped or failed: {e}")

    # Initialize the Analysis Engine (LangGraph Edition)
    engine = await get_engine()
    try:
        await engine.initialize()
        logger.info("✓ Analysis Engine initialized (LangGraph, A2A)")
    except Exception as e:
        logger.warning(f"✗ Engine initialization partial: {e}")
        logger.info("  Some MCP servers may be unavailable. Analysis may be limited.")

    logger.info("=" * 60)
    logger.info("Quant Research Engine — Ready!")
    logger.info("=" * 60)

    yield  # App runs here

    logger.info("Shutting down Quant Research Engine...")


# ══════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ══════════════════════════════════════════════════════════════

app = FastAPI(
    title="Quant Research Engine",
    description=(
        "Autonomous Financial Analysis Engine — Generates structured investment "
        "memos using AI-powered tool calling, MCP servers, and real-time market data. "
        "Built with native Google GenAI SDK, no heavy frameworks."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS (for frontend) ──────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── STATIC FILES ─────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(os.path.join(STATIC_DIR, "charts"), exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ══════════════════════════════════════════════════════════════
# API ENDPOINTS
# ══════════════════════════════════════════════════════════════


@app.get("/api/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint. Returns service status and engine information.
    """
    services = {
        "database": "unknown",
        "engine": "initialized" if engine and engine._initialized else "not_initialized",
        "mcp_servers": {},
    }

    # Check database
    try:
        from backend.data.database import async_engine
        from sqlalchemy import text

        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        services["database"] = "connected"
    except Exception:
        services["database"] = "disconnected"

    # Check MCP server connections
    if engine:
        services["mcp_servers"] = engine.tool_registry.get_server_info()
        services["available_tools"] = engine.tool_registry.get_tool_names()

    return HealthResponse(
        status="healthy" if services["database"] == "connected" else "degraded",
        version="1.0.0",
        services=services,
        timestamp=datetime.utcnow().isoformat(),
    )


@app.post("/api/analyze", response_model=AnalyzeResponse, tags=["Analysis"])
async def analyze(request: AnalyzeRequest):
    """
    Submit a natural language query for AI-powered financial analysis.

    The engine will:
    1. Validate the query (input guardrails)
    2. Use Gemini API with tool-calling to fetch real financial data
    3. Generate a structured investment memo
    4. Run a critic review for quality assurance
    5. Apply output guardrails (PII check, disclaimer)

    Example queries:
    - "Analyze NVIDIA stock"
    - "Compare AAPL vs MSFT for investment"
    - "Give me a buy/sell brief on AMD vs INTC"
    - "What are the best semiconductor stocks by P/E ratio?"
    """
    if not engine or not engine._initialized:
        raise HTTPException(
            status_code=503,
            detail="Analysis engine is not initialized. MCP servers may be starting up.",
        )

    logger.info(f"Analysis request: {request.query[:100]}...")

    result = await engine.analyze(
        query=request.query,
        include_critique=request.include_critique,
    )

    if result["error"]:
        return AnalyzeResponse(
            success=False,
            error=result["error"],
            warnings=result.get("warnings", []),
        )

    return AnalyzeResponse(
        success=True,
        report=result["report"],
        critique=result["critique"],
        metadata=result["metadata"],
        warnings=result.get("warnings", []),
    )


@app.post("/api/analyze/stream", tags=["Analysis"])
async def analyze_stream(request: AnalyzeRequest):
    """
    Streaming analysis endpoint using Server-Sent Events (SSE).

    Returns real-time progress updates as the analysis proceeds:
    - status: Progress messages
    - tool_call: When a tool is being called
    - report: The final report
    - critique: The critic review
    - error: Any errors
    """
    if not engine or not engine._initialized:
        raise HTTPException(
            status_code=503,
            detail="Analysis engine is not initialized.",
        )

    async def event_generator():
        async for event in engine.analyze_stream(request.query):
            yield f"data: {json.dumps(event)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/seed", response_model=SeedResponse, tags=["Data"])
async def seed_database(request: SeedRequest, background_tasks: BackgroundTasks):
    """
    Trigger database seeding with S&P 500 stock data from yfinance.

    This runs in the background and populates the PostgreSQL database
    with stock fundamentals, historical prices, and earnings data.

    If no tickers are specified, seeds the default top 50 S&P 500 stocks.
    """
    from backend.data.seed_database import fetch_and_seed_stocks, SP500_TOP_50

    tickers = request.tickers or SP500_TOP_50

    # Run seeding in background to avoid timeout
    background_tasks.add_task(fetch_and_seed_stocks, tickers)

    return SeedResponse(
        success=True,
        message=f"Database seeding started for {len(tickers)} tickers. "
        f"This will run in the background.",
        tickers_seeded=tickers,
    )


@app.get("/api/tools", tags=["System"])
async def list_tools():
    """
    List all available tools registered from MCP servers.
    """
    if not engine:
        return {"tools": [], "message": "Engine not initialized"}

    return {
        "tools": engine.tool_registry.get_tool_names(),
        "servers": engine.tool_registry.get_server_info(),
        "declarations": engine.tool_registry.get_genai_declarations(),
    }


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
    )
