import streamlit as st
from datetime import datetime


# ── 导航分组定义 ────────────────────────────────────────────────
_CORE_NAV = [
    ("📡 实时看盘", "market",    "信号 · 赛道 · 策略"),
    ("🎯 AI荐股",  "recommend", "多策略共振 · 综合推荐"),
    ("🧬 深度研究", "research",  "DNA · 估值 · 财报"),
    ("💼 资产管理", "portfolio", "持仓 · 收益 · 回测"),
]

_AI_NAV = [
    ("📡 信号追踪", "ai_tracker",          "实时 AI 信号流"),
    ("💬 AI策略师", "ai_chat",             "对话式量化顾问"),
    ("💡 投顾建议", "investment_advisor",  "组合优化建议"),
    ("🎭 情绪雷达", "sentiment",           "市场情绪分析"),
]

_LAB_NAV = [
    ("📊 宏观雷达", "macro",             "经济指标监控"),
    ("🔍 异动监测", "anomaly",           "异常成交探测"),
    ("🔬 预测中心", "predict",           "AI 价格预测"),
    ("🛠️ 技术回测", "backtest",          "策略历史验证"),
    ("🧪 研究员台", "research_analyzer", "深度研究分析"),
]

_OPS_NAV = [
    ("🔌 数据管理",    "data_manager", "数据源配置"),
    ("🩺 数据健康",    "data_health",  "连接 & 新鲜度"),
    ("🔔 预警中心",    "alerts",       "多渠道告警"),
    ("⚙️ 系统设置",    "settings",     "参数配置"),
]

_SIDEBAR_STYLE = ""


def _nav_btn(label: str, page: str, current: str, hint: str = ""):
    is_active = current == page
    if st.button(
        label,
        key=f"PRO_SSM_V7_sidebar_{page}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
        help=hint or None,
    ):
        st.session_state["current_page"] = page
        st.rerun()


def render_sidebar(L, name_map, new_modules_available=True):
    """渲染全局侧边栏导航 v8.0 — 精品机构版"""
    # CSS 已在 style.css 中定义，无需内联注入

    current = st.session_state.get("current_page", "market")

    with st.sidebar:
        # ── 品牌区 ────────────────────────────────────────────
        now_h = datetime.now().hour
        market_open = 9 <= now_h < 15
        dot_color = "#10b981" if market_open else "#f59e0b"
        status_text = "交易中" if market_open else "已收盘"

        st.markdown(
            f"""<div class="ssm-brand">
                <div class="ssm-brand-logo">SSM QUANT</div>
                <div class="ssm-brand-sub">
                    <span class="ssm-brand-dot" style="background:{dot_color};"></span>
                    {status_text} · Institutional v8.0
                </div>
            </div>""",
            unsafe_allow_html=True,
        )

        # ── 用户菜单 ──────────────────────────────────────────
        try:
            from pages._login import render_user_menu
            render_user_menu()
            st.divider()
        except ImportError:
            pass

        # ── 核心导航 ──────────────────────────────────────────
        for label, page, hint in _CORE_NAV:
            _nav_btn(label, page, current, hint)

        st.divider()

        # ── AI 策略矩阵 ───────────────────────────────────────
        with st.expander("🤖 AI 策略矩阵", expanded=False):
            for label, page, hint in _AI_NAV:
                _nav_btn(label, page, current, hint)

        # ── 量化实验室 ────────────────────────────────────────
        with st.expander("🔬 量化实验室", expanded=False):
            for label, page, hint in _LAB_NAV:
                _nav_btn(label, page, current, hint)

        # ── 系统运维 ──────────────────────────────────────────
        with st.expander("⚙️ 系统运维", expanded=False):
            for label, page, hint in _OPS_NAV:
                _nav_btn(label, page, current, hint)

        st.divider()

        # ── 快捷标的入口 ──────────────────────────────────────
        try:
            from components.ui_components import stock_context_bar
            stock_context_bar(name_map)
        except Exception:
            pass

        # 首次初始化：默认代码 601933（只设一次，不覆盖用户输入）
        if 'ssm_quick_code_input' not in st.session_state:
            st.session_state['ssm_quick_code_input'] = \
                st.session_state.get('selected_stock', '601933')

        quick_code = st.text_input(
            "快捷分析",
            key="ssm_quick_code_input",
            placeholder="输入股票代码",
        )
        if st.button(
            "🔬 开始深度分析",
            key="ssm_quick_code_go",
            use_container_width=True,
            type="primary",
        ):
            code = quick_code.strip() if quick_code and quick_code.strip() else '601933'
            st.session_state['selected_stock'] = code
            st.session_state['current_page'] = 'market'
            st.session_state['market_view'] = '📊 深度分析'
            st.rerun()


        # ── 自选计数 + 页脚 ───────────────────────────────────
        wl = L.get("watchlist", []) if isinstance(L, dict) else []
        wl_count = len(wl) if wl else 0

        st.html(
            f'<div class="ssm-footer">'
            f'<div class="ssm-footer-inner">'
            f'<span class="ssm-version">v8.0</span>'
            f'&nbsp;SSM Quantum Pro<br>'
            f'⭐ 自选 {wl_count} 只 · AI 量化投研工作站'
            f'</div></div>'
        )
