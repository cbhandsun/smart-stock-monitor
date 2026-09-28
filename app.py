"""Smart Stock Monitor application composition root."""

from __future__ import annotations

import importlib
import logging
import os
from pathlib import Path

import streamlit as st

from core.routing import DEFAULT_PAGE, DEFAULT_SYMBOL, parse_page, parse_symbol
from core.theme import Theme, parse_theme
from database.models import init_db
from main import get_stock_names_batch
from pages import load_watchlist


logger = logging.getLogger(__name__)

L = {
    "market_discovery": "实时信号流",
    "stock_dna": "研判 DNA",
    "alpha_radar": "宏观雷达",
    "ai_analyst": "AI 策略师",
    "anomaly_detect": "异动监控",
}
NEW_MODULES_AVAILABLE = True


def _load_styles(theme: Theme) -> None:
    try:
        style_path = Path("static/style.css")
        if not style_path.is_file():
            raise OSError("style asset is missing")
        st.html(style_path)
        if theme == "light":
            light_style_path = Path("static/light-theme.css")
            if not light_style_path.is_file():
                raise OSError("light theme asset is missing")
            st.html(light_style_path)
    except OSError:
        logger.warning("Custom styles are unavailable; using Streamlit defaults")


def _require_authentication() -> None:
    try:
        from pages._login import check_auth, render_login_page
    except ImportError:
        logger.error("Security gatekeeper failed to load")
        st.error("🚨 系统安全组件无法加载，访问已中止。请联系管理员。")
        st.stop()

    if not check_auth():
        render_login_page()
        st.stop()


def _sync_navigation_state() -> tuple[str, str]:
    query_page = parse_page(st.query_params.get("page"))
    query_symbol = parse_symbol(st.query_params.get("symbol"))

    current_page = parse_page(st.session_state.get("current_page", query_page))
    selected_stock = parse_symbol(st.session_state.get("selected_stock", query_symbol))

    if query_page != parse_page(st.session_state.get("_last_query_page")):
        current_page = query_page
    if query_symbol != parse_symbol(st.session_state.get("_last_query_symbol")):
        selected_stock = query_symbol

    st.session_state["current_page"] = current_page
    st.session_state["selected_stock"] = selected_stock
    st.session_state["_last_query_page"] = current_page
    st.session_state["_last_query_symbol"] = selected_stock

    if st.query_params.get("page") != current_page:
        st.query_params["page"] = current_page
    if st.query_params.get("symbol") != selected_stock:
        st.query_params["symbol"] = selected_stock
    return current_page, selected_stock


def _load_page(page_name: str):
    safe_page = parse_page(page_name)
    try:
        return importlib.import_module(f"pages.{safe_page}")
    except (ImportError, AttributeError):
        logger.error("Failed to load an allowed application page")
        return None


def _render_page(page_name: str, render_args: tuple[object, ...]) -> None:
    module = _load_page(page_name)
    render = getattr(module, "render", None) if module else None
    if not callable(render):
        st.error("当前页面暂时不可用，请返回市场首页后重试。")
        if st.button("返回市场首页", type="primary"):
            st.session_state["current_page"] = DEFAULT_PAGE
            st.rerun()
        return
    render(*render_args)


def main() -> None:
    init_db(os.environ.get("DATABASE_URL", "sqlite:///./data/stock_monitor.db"))
    theme = parse_theme(st.session_state.get("theme"))
    st.session_state["theme"] = theme
    _load_styles(theme)
    _require_authentication()

    current_page, _ = _sync_navigation_state()
    try:
        my_stocks = load_watchlist()
    except Exception:
        logger.error("Watchlist preload failed")
        st.error("自选股暂时无法加载；其他页面仍可使用，请稍后重试。")
        my_stocks = []
    try:
        name_map = get_stock_names_batch(
            list(my_stocks) + ["300750", "600519", "000001", DEFAULT_SYMBOL]
        )
    except Exception:
        logger.error("Stock name preload failed")
        name_map = {}

    page_render_args = {
        "macro": (L,),
        "market": (L, my_stocks, name_map),
        "recommend": (L, my_stocks, name_map),
        "ai_tracker": (L, my_stocks, name_map),
        "settings": (L, NEW_MODULES_AVAILABLE),
        "data_manager": (L,),
        "data_health": (L,),
        "research_analyzer": (L, name_map),
        "portfolio": (L,),
        "alerts": (L,),
        "backtest": (L,),
        "research": (L, my_stocks, name_map),
        "ai_chat": (L,),
        "predict": (L,),
        "sentiment": (L, my_stocks, name_map),
        "anomaly": (L, my_stocks, name_map),
        "investment_advisor": (L,),
    }

    try:
        from components.sidebar import render_sidebar

        render_sidebar({**L, "watchlist": my_stocks}, name_map, NEW_MODULES_AVAILABLE)
    except Exception:
        logger.error("Sidebar failed to render")
        st.sidebar.error("侧边栏加载失败，请刷新后重试。")

    _render_page(current_page, page_render_args[current_page])


main()
