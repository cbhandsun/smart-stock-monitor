"""Theme state parsing shared by the application shell and settings page."""

from __future__ import annotations

from typing import Literal


Theme = Literal["dark", "light"]
DEFAULT_THEME: Theme = "dark"
SUPPORTED_THEMES: tuple[Theme, ...] = ("dark", "light")


def parse_theme(value: object) -> Theme:
    """Coerce untrusted session state to a supported theme value."""
    if isinstance(value, str) and value in SUPPORTED_THEMES:
        return value
    return DEFAULT_THEME
