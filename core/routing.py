"""Allowlisted parsing for URL-controlled application routing state."""

from __future__ import annotations

import re


DEFAULT_PAGE = "market"
DEFAULT_SYMBOL = "601933"
ALLOWED_PAGES = frozenset(
    {
        "macro",
        "market",
        "recommend",
        "ai_tracker",
        "settings",
        "data_manager",
        "data_health",
        "research_analyzer",
        "portfolio",
        "alerts",
        "backtest",
        "research",
        "ai_chat",
        "predict",
        "sentiment",
        "anomaly",
        "investment_advisor",
    }
)
_SYMBOL_RE = re.compile(r"^\d{6}$")


def parse_page(value: object) -> str:
    """Coerce an untrusted route value to a known page."""
    if isinstance(value, str) and value in ALLOWED_PAGES:
        return value
    return DEFAULT_PAGE


def parse_symbol(value: object) -> str:
    """Coerce an untrusted stock symbol to a six-digit A-share code."""
    if isinstance(value, str) and _SYMBOL_RE.fullmatch(value):
        return value
    return DEFAULT_SYMBOL
