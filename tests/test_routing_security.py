"""Regression tests for URL route and stock-symbol allowlists."""

import pytest

from core.routing import DEFAULT_PAGE, DEFAULT_SYMBOL, parse_page, parse_symbol


@pytest.mark.parametrize(
    "value",
    [None, "", "../../auth/user_auth", "__init__", "portfolio;drop", ["market"]],
)
def test_invalid_page_falls_back_to_market(value):
    assert parse_page(value) == DEFAULT_PAGE


@pytest.mark.parametrize("value", [None, "", "ABC123", "60051", "6005190", "../../etc"])
def test_invalid_symbol_falls_back_to_safe_default(value):
    assert parse_symbol(value) == DEFAULT_SYMBOL


def test_allowed_page_and_symbol_are_preserved():
    assert parse_page("portfolio") == "portfolio"
    assert parse_symbol("600519") == "600519"
