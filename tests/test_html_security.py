"""Security regression tests for the global Streamlit HTML boundary."""

import pytest

from core.html_security import install_streamlit_html_guard, sanitize_html


def test_sanitizer_removes_executable_markup_and_unsafe_urls():
    cleaned = sanitize_html(
        '<script>alert(1)</script><img src="javascript:alert(1)" onerror="alert(2)">'
        '<a href="https://example.com">safe</a>'
    )
    assert "script" not in cleaned
    assert "onerror" not in cleaned
    assert "javascript:" not in cleaned
    assert 'href="https://example.com"' in cleaned


def test_sanitizer_filters_dangerous_css_and_rejects_unknown_input():
    cleaned = sanitize_html(
        '<div style="color:red;position:fixed;background-image:url(https://evil.invalid/x)">x</div>'
    )
    assert "color:red" in cleaned
    assert "position:fixed" not in cleaned
    assert "background-image" not in cleaned
    with pytest.raises(TypeError):
        sanitize_html(None)


def test_global_guard_sanitizes_html_and_unsafe_markdown_once():
    calls = []

    class FakeStreamlit:
        def html(self, body, *args, **kwargs):
            calls.append(("html", body))

        def markdown(self, body, *args, **kwargs):
            calls.append(("markdown", body))

    fake = FakeStreamlit()
    install_streamlit_html_guard(fake)
    install_streamlit_html_guard(fake)
    fake.html('<img src="x" onerror="alert(1)">')
    fake.markdown("<script>alert(1)</script><b>safe</b>", unsafe_allow_html=True)
    assert fake.html("<script>alert(1)</script>") is None

    assert "onerror" not in calls[0][1]
    assert calls[1][1] == "<b>safe</b>"
    assert len(calls) == 2
