"""
Quant Research Engine — AI Safety Guardrails

Input/Output guardrails for the orchestrator. Implements:
  1. Input sanitization — validates and cleans user queries
  2. SQL injection prevention — blocks dangerous SQL patterns
  3. Output validation — ensures report quality and safety

Design Philosophy:
  Saxo Bank JD: "Security and privacy awareness, including risks specific
  to LLM-based systems." These guardrails demonstrate production-grade
  security thinking.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# INPUT GUARDRAILS
# ══════════════════════════════════════════════════════════════

# Maximum allowable input length
MAX_INPUT_LENGTH = 1000

# Patterns that indicate prompt injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"disregard\s+(all\s+)?previous",
    r"forget\s+(all\s+)?previous",
    r"system\s*prompt",
    r"you\s+are\s+now",
    r"pretend\s+to\s+be",
    r"act\s+as\s+if",
    r"bypass\s+",
    r"override\s+",
    r"jailbreak",
    r"DAN\s+mode",
]

# Topics that are out of scope for a financial analyst
OUT_OF_SCOPE_PATTERNS = [
    r"hack\b",
    r"exploit\b",
    r"password",
    r"credential",
    r"private\s+key",
    r"social\s+security",
    r"credit\s+card\s+number",
]


def validate_user_input(query: str) -> tuple[bool, str, Optional[str]]:
    """
    Validate and sanitize user input.

    Returns:
        (is_valid, sanitized_query, error_message)
    """
    if not query or not query.strip():
        return False, "", "Please provide a query to analyze."

    query = query.strip()

    # Check length
    if len(query) > MAX_INPUT_LENGTH:
        return False, "", (
            f"Query is too long ({len(query)} chars). "
            f"Maximum allowed is {MAX_INPUT_LENGTH} characters."
        )

    # Check for prompt injection
    query_lower = query.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            logger.warning(f"Prompt injection detected: {query[:100]}...")
            return False, "", (
                "Your query contains patterns that look like prompt injection. "
                "Please rephrase your financial analysis request."
            )

    # Check for out-of-scope topics
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            logger.warning(f"Out-of-scope query detected: {query[:100]}...")
            return False, "", (
                "This system is designed for financial analysis only. "
                "Please ask about stocks, markets, or investment analysis."
            )

    return True, query, None


# ══════════════════════════════════════════════════════════════
# SQL GUARDRAILS
# ══════════════════════════════════════════════════════════════

BLOCKED_SQL_KEYWORDS = [
    "DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "EXEC", "EXECUTE",
    "COPY", "LOAD", "VACUUM", "REINDEX", "CLUSTER",
]

BLOCKED_SQL_PATTERNS = [
    r";--",           # SQL comment injection
    r"/\*.*\*/",      # Block comments
    r"xp_\w+",        # Extended procedures
    r"sp_\w+",        # Stored procedures
    r"pg_\w+",        # PostgreSQL system functions
    r"INFORMATION_SCHEMA",  # Schema enumeration
    r"pg_catalog",    # System catalog
]


def validate_sql(query: str) -> tuple[bool, str]:
    """
    Validate that a SQL query is safe for execution.

    This is the critical security layer that prevents SQL injection
    from AI-generated queries. The MCP server has its own guardrails too,
    providing defense-in-depth.

    Returns:
        (is_safe, error_message)
    """
    if not query or not query.strip():
        return False, "Empty SQL query."

    normalized = " ".join(query.upper().split())

    # Must start with SELECT or WITH (CTEs)
    if not (normalized.startswith("SELECT") or normalized.startswith("WITH")):
        return False, f"Only SELECT queries allowed. Got: {normalized[:30]}..."

    # Check for blocked keywords
    for keyword in BLOCKED_SQL_KEYWORDS:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, normalized):
            return False, f"Blocked SQL keyword: {keyword}"

    # Check for blocked patterns
    for pattern in BLOCKED_SQL_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            return False, f"Blocked SQL pattern detected."

    # Check for multiple statements
    stripped = query.strip().rstrip(";")
    if ";" in stripped:
        return False, "Multiple SQL statements not allowed."

    return True, ""


# ══════════════════════════════════════════════════════════════
# OUTPUT GUARDRAILS
# ══════════════════════════════════════════════════════════════

# PII patterns to check for in output
PII_PATTERNS = [
    (r'\b\d{3}-\d{2}-\d{4}\b', "SSN"),
    (r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b', "credit card"),
    (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', "email"),
]

# Disclaimer that should be added to financial reports
FINANCIAL_DISCLAIMER = (
    "\n\n---\n"
    "*⚠️ Disclaimer: This report is generated by an AI system for informational purposes only. "
    "It does not constitute financial advice, investment recommendations, or solicitation to buy "
    "or sell securities. Past performance is not indicative of future results. Always consult with "
    "a qualified financial advisor before making investment decisions.*"
)


def validate_output(report: str) -> tuple[str, list[str]]:
    """
    Validate and enhance the AI-generated report.

    Checks for:
      - PII leakage
      - Adds financial disclaimer
      - Flags potential issues

    Returns:
        (cleaned_report, warnings_list)
    """
    warnings = []

    # Check for PII
    for pattern, pii_type in PII_PATTERNS:
        if re.search(pattern, report):
            warnings.append(f"Potential {pii_type} detected in output — redacted.")
            report = re.sub(pattern, f"[REDACTED {pii_type.upper()}]", report)

    # Add financial disclaimer if not present
    if "disclaimer" not in report.lower():
        report += FINANCIAL_DISCLAIMER

    return report, warnings


def check_report_quality(report: str) -> tuple[bool, list[str]]:
    """
    Check if the report meets minimum quality standards.

    Returns:
        (passes_quality_check, issues_list)
    """
    issues = []

    if len(report) < 200:
        issues.append("Report is too short (less than 200 characters).")

    # Check for key sections
    expected_sections = ["summary", "analysis", "recommendation"]
    report_lower = report.lower()
    for section in expected_sections:
        if section not in report_lower:
            issues.append(f"Report may be missing '{section}' section.")

    return len(issues) == 0, issues
