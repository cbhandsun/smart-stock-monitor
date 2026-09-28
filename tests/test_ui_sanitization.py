"""Regression tests for dynamic values interpolated into custom HTML."""

from components.ui_components import _color, _html, status_badge_html


def test_dynamic_html_values_are_escaped():
    assert _html('<img src=x onerror="alert(1)">') == (
        "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;"
    )


def test_css_color_rejects_injected_style_value():
    assert _color("red; background:url(javascript:alert(1))") == "#38bdf8"
    assert _color("#A1B2C3") == "#A1B2C3"


def test_badge_level_is_allowlisted_and_text_is_escaped():
    badge = status_badge_html("<script>alert(1)</script>", "x onclick=alert(1)")
    assert "badge-info" in badge
    assert "<script>" not in badge
    assert "&lt;script&gt;" in badge
