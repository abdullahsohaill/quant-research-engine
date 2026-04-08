"""
Quant Research Engine — API Schemas

Pydantic models for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ══════════════════════════════════════════════════════════════


class AnalyzeRequest(BaseModel):
    """Request body for the /api/analyze endpoint."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural language query for financial analysis",
        examples=[
            "Analyze NVIDIA stock",
            "Compare AAPL vs MSFT for investment",
            "Give me a buy/sell brief on AMD",
        ],
    )
    include_critique: bool = Field(
        default=True,
        description="Whether to include critic agent review",
    )


class SeedRequest(BaseModel):
    """Request body for the /api/seed endpoint."""

    tickers: Optional[list[str]] = Field(
        default=None,
        description="Optional list of specific tickers to seed. "
        "If not provided, seeds the default top 50 S&P 500.",
    )


# ══════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ══════════════════════════════════════════════════════════════


class ToolCallInfo(BaseModel):
    """Information about a single tool call made during analysis."""

    tool: str
    args: dict
    iteration: int
    status: str
    result_length: Optional[int] = None
    error: Optional[str] = None


class AnalysisMetadata(BaseModel):
    """Metadata about the analysis execution."""

    query: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_seconds: Optional[float] = None
    iterations: int = 0
    tool_calls: list[ToolCallInfo] = []
    model: str = ""


class AnalyzeResponse(BaseModel):
    """Response body for the /api/analyze endpoint."""

    success: bool
    report: Optional[str] = None
    critique: Optional[str] = None
    metadata: Optional[AnalysisMetadata] = None
    warnings: list[str] = []
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Response body for the /api/health endpoint."""

    status: str
    version: str
    services: dict
    timestamp: str


class SeedResponse(BaseModel):
    """Response body for the /api/seed endpoint."""

    success: bool
    message: str
    tickers_seeded: Optional[list[str]] = None
    error: Optional[str] = None


# ══════════════════════════════════════════════════════════════
# SSE EVENT MODELS
# ══════════════════════════════════════════════════════════════


class StreamEvent(BaseModel):
    """A single Server-Sent Event during streaming analysis."""

    type: str = Field(description="Event type: status, tool_call, report, critique, error, metadata")
    data: str | dict = Field(description="Event payload")
