"""
📡 市场信号流 — V9.1 精简头部版
"""
import streamlit as st

from pages.market._bar import _render_market_bar
from pages.market._strategy import _render_strategy_view
from pages.market._views import _render_analyze_view, _render_track_view

# 兼容性导出
from pages.market._signals import _get_quick_signals, _batch_get_all_signals
from pages.market._card import (
    _render_stock_card,
    _render_stock_list,
    _render_tag_filter_bar,
    _render_generic_strategy_tab,
)

# ── 内联 UI 补丁 (仅限 market 页面) ────────────────────────────
_MARKET_STYLE = ""  # CSS 已在 style.css 中定义


def render(L, my_stocks, name_map):
    """渲染市场页面"""
    st.html(_MARKET_STYLE)

    # ── 大盘指数条 ────────────────────────────────────────────
    _render_market_bar()

    # ── 页面标题 + 视图导航 ───────────────────────────────────
    if 'market_view' not in st.session_state:
        st.session_state['market_view'] = '📋 策略选股'

    views = ['📋 策略选股', '📊 深度分析', '⭐ 自选跟盘']

    view_map_rev = {
        'strategy': '📋 策略选股',
        'analyze':  '📊 深度分析',
        'track':    '⭐ 自选跟盘',
    }
    current_view = st.session_state.get('market_view', '📋 策略选股')
    if current_view in view_map_rev:
        current_view = view_map_rev[current_view]

    # 标题 + 导航一行排列
    hcol, nav_col, stat_col = st.columns([2, 4, 2])
    with hcol:
        st.markdown(
            '<div class="market-page-header">'
            '<span class="market-page-title">📡 市场信号流</span>'
            '<span class="market-page-badge">LIVE</span>'
            '</div>',
            unsafe_allow_html=True
        )
    with nav_col:
        selected_view = st.segmented_control(
            "视图",
            options=views,
            default=current_view,
            label_visibility="collapsed",
            key="market_view_router",
        )
    with stat_col:
        wl_count = len(my_stocks)
        st.markdown(
            f'<div style="text-align:right; padding-top:4px;">'
            f'<span style="font-size:0.75rem; color:#64748b;">自选</span> '
            f'<span style="font-size:1rem; font-weight:700; color:#38bdf8; font-family:\'JetBrains Mono\',monospace;">'
            f'{wl_count}</span> '
            f'<span style="font-size:0.75rem; color:#64748b;">只</span>'
            f'</div>',
            unsafe_allow_html=True
        )

    if selected_view:
        st.session_state['market_view'] = selected_view

    st.markdown('<hr style="margin:8px 0 16px; opacity:0.3;">', unsafe_allow_html=True)

    # ── 路由分发 ──────────────────────────────────────────────
    active_view = st.session_state['market_view']
    if active_view in ('📋 策略选股', 'strategy'):
        _render_strategy_view(L, my_stocks, name_map)
    elif active_view in ('📊 深度分析', 'analyze'):
        _render_analyze_view(L, my_stocks, name_map)
    elif active_view in ('⭐ 自选跟盘', 'track'):
        _render_track_view(L, my_stocks, name_map)
