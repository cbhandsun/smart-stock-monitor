"""Server-side HTML sanitization for every Streamlit HTML rendering path."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import nh3


_TAGS = {
    "a",
    "b",
    "blockquote",
    "br",
    "caption",
    "code",
    "col",
    "colgroup",
    "div",
    "em",
    "figcaption",
    "figure",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "i",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "small",
    "span",
    "strong",
    "sub",
    "sup",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
}
_ATTRIBUTES = {
    "*": {"class", "id", "role", "style", "title"},
    "a": {"href", "target"},
    "img": {"alt", "height", "src", "width"},
    "td": {"colspan", "rowspan"},
    "th": {"colspan", "rowspan", "scope"},
}
_STYLE_PROPERTIES = {
    "align-items",
    "animation",
    "animation-delay",
    "background",
    "background-color",
    "border",
    "border-bottom",
    "border-color",
    "border-left",
    "border-radius",
    "border-right",
    "border-top",
    "bottom",
    "box-shadow",
    "color",
    "display",
    "flex",
    "flex-direction",
    "flex-wrap",
    "font-family",
    "font-size",
    "font-style",
    "font-weight",
    "gap",
    "grid-template-columns",
    "height",
    "justify-content",
    "left",
    "letter-spacing",
    "line-height",
    "margin",
    "margin-bottom",
    "margin-left",
    "margin-right",
    "margin-top",
    "max-width",
    "min-height",
    "min-width",
    "opacity",
    "overflow",
    "overflow-x",
    "padding",
    "padding-bottom",
    "padding-left",
    "padding-right",
    "padding-top",
    "right",
    "text-align",
    "text-decoration",
    "text-overflow",
    "text-transform",
    "top",
    "transform",
    "transition",
    "vertical-align",
    "white-space",
    "width",
    "word-break",
}


def sanitize_html(value: object) -> str:
    """Return a safe HTML fragment; unknown input is rejected rather than coerced."""
    if not isinstance(value, str):
        raise TypeError("HTML content must be a string")
    if len(value) > 1_000_000:
        raise ValueError("HTML content is too large")
    return nh3.clean(
        value,
        tags=_TAGS,
        clean_content_tags={"script", "style", "iframe", "object", "embed"},
        attributes=_ATTRIBUTES,
        generic_attribute_prefixes={"aria-", "data-"},
        filter_style_properties=_STYLE_PROPERTIES,
        url_schemes={"https", "mailto"},
        url_relative="deny",
    )


class _StreamlitHtmlModule(Protocol):
    html: Callable[..., object]
    markdown: Callable[..., object]


def install_streamlit_html_guard(streamlit_module: _StreamlitHtmlModule) -> None:
    """Wrap Streamlit's raw HTML APIs once at the process composition root."""
    if getattr(streamlit_module, "_ssm_html_guard_installed", False):
        return
    original_html = streamlit_module.html
    original_markdown = streamlit_module.markdown

    def guarded_html(body: object, *args: object, **kwargs: object) -> object:
        if isinstance(body, str):
            body = sanitize_html(body)
            if not body.strip():
                return None
        return original_html(body, *args, **kwargs)

    def guarded_markdown(body: object, *args: object, **kwargs: object) -> object:
        if kwargs.get("unsafe_allow_html") is True:
            body = sanitize_html(body)
        return original_markdown(body, *args, **kwargs)

    streamlit_module.html = guarded_html
    streamlit_module.markdown = guarded_markdown
    setattr(streamlit_module, "_ssm_html_guard_installed", True)
