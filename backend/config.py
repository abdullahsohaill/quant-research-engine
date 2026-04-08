"""
Quant Research Engine — Configuration

Centralized settings management using pydantic-settings.
Reads from environment variables and .env file.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── API Keys ──────────────────────────────────────────────
    gemini_api_key: str = ""
    hf_token: str = ""

    # ── Database ──────────────────────────────────────────────
    postgres_user: str = "quant_user"
    postgres_password: str = "quant_password"
    postgres_db: str = "quant_research"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ── Backend Server ────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # ── MCP Servers ───────────────────────────────────────────
    financial_mcp_host: str = "0.0.0.0"
    financial_mcp_port: int = 8001
    postgres_mcp_host: str = "0.0.0.0"
    postgres_mcp_port: int = 8002
    email_mcp_host: str = "0.0.0.0"
    email_mcp_port: int = 8003

    # ── Gemini Models ─────────────────────────────────────────
    gemini_model: str = "gemini-2.5-flash"
    gemini_critic_model: str = "gemini-2.5-flash"

    # ── Orchestrator ──────────────────────────────────────────
    max_tool_iterations: int = 15
    max_tokens: int = 8192

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
