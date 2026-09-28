"""
统一的 UI 组件：页面头部、全局标的指示器、股票选择器、跨页导航
"""

from html import escape
import re

import streamlit as st

from core.routing import parse_page, parse_symbol


_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _html(value: object) -> str:
    return escape(str(value), quote=True)


def _color(value: object, fallback: str = "#38bdf8") -> str:
    return (
        str(value)
        if isinstance(value, str) and _COLOR_RE.fullmatch(value)
        else fallback
    )


def page_header(title, subtitle="", icon=""):
    """统一的页面头部组件"""
    title = _html(title)
    subtitle = _html(subtitle)
    icon = _html(icon)
    sub_html = (
        f"<span style='color:#64748b; font-size:0.85rem; margin-left:12px;'>{subtitle}</span>"
        if subtitle
        else ""
    )
    st.html(f"""
<div style="margin-bottom: 16px;">
    <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 700; color: #f1f5f9;">
        {icon} {title}{sub_html}
    </div>
</div>
""")


def stock_context_bar(name_map):
    """全局标的指示器 — 始终显示当前分析的股票"""
    current = st.session_state.get("selected_stock", "601318")
    current = parse_symbol(current)
    cur_name = _html(name_map.get(current, ""))
    current = _html(current)

    st.html(f"""
<div style="background: rgba(30,41,59,0.35); border: 1px solid rgba(255,255,255,0.05);
     border-radius: 10px; padding: 6px 16px; margin-bottom: 12px;
     display: flex; align-items: center; gap: 10px; font-size: 0.82rem;">
    <span style="color: #64748b;">当前标的</span>
    <span style="color: #38bdf8; font-weight: 600;">{current}</span>
    <span style="color: #94a3b8;">{cur_name}</span>
</div>
""")


def stock_selector(label="分析标的", key_suffix="default"):
    """
    统一的股票代码选择器。
    修改后自动同步到 session_state['selected_stock']。
    返回: 当前选中的股票代码字符串
    """
    current = st.session_state.get("selected_stock", "601318")
    current = parse_symbol(current)
    new_val = st.text_input(
        label, value=current, key=f"PRO_SSM_V7_stock_sel_{key_suffix}"
    )

    # 同步回 session_state
    parsed_value = parse_symbol(new_val)
    if new_val and parsed_value != new_val:
        st.caption("股票代码需为6位数字，已保留原标的。")
        return current
    if parsed_value != current:
        st.session_state["selected_stock"] = parsed_value

    return parsed_value


def nav_to_page(
    target_page,
    label,
    icon="→",
    stock_code=None,
    button_type="secondary",
    key_suffix="",
):
    """
    跨页面导航按钮。
    点击后跳转到目标页面，可选地设置分析标的。
    """
    # 使用 PRO_SSM_V7_ 命名空间前缀
    target_page = parse_page(target_page)
    clean_label = "".join(filter(str.isalnum, str(label)))
    btn_key = f"PRO_SSM_V7_nav_{target_page}_{clean_label}_{key_suffix}"
    if st.button(
        f"{icon} {label}", key=btn_key, type=button_type, use_container_width=True
    ):
        if stock_code:
            st.session_state["selected_stock"] = parse_symbol(stock_code)
        st.session_state["current_page"] = target_page
        st.rerun()


def info_card(title, value, subtitle="", icon="", color="#38bdf8"):
    """Glassmorphism 信息卡片 — 利用 CSS .ssm-card 样式"""
    title = _html(title)
    value = _html(value)
    subtitle = _html(subtitle)
    icon = _html(icon)
    color = _color(color)
    icon_html = (
        f'<span style="font-size:1.4rem; margin-right:8px;">{icon}</span>'
        if icon
        else ""
    )
    sub_html = f'<div class="ssm-card-sub">{subtitle}</div>' if subtitle else ""
    st.html(f"""<div class="ssm-card">
    <div class="ssm-card-title">{icon_html}{title}</div>
    <div class="ssm-card-value" style="color:{color};">{value}</div>
    {sub_html}
</div>""")


def empty_state(
    icon="📋", title="暂无数据", description="", action_label=None, action_key=None
):
    """空状态占位面板 — 居中图标 + 说明文字 + 可选操作按钮"""
    icon = _html(icon)
    title = _html(title)
    description = _html(description)
    st.html(f"""<div class="empty-state">
    <div class="empty-state-icon">{icon}</div>
    <div class="empty-state-title">{title}</div>
    <div class="empty-state-desc">{description}</div>
</div>""")
    if action_label and action_key:
        _, center, _ = st.columns([2, 1, 2])
        with center:
            final_key = f"PRO_SSM_V7_empty_{action_key}"
            return st.button(
                action_label, key=final_key, type="primary", use_container_width=True
            )
    return False


def status_badge_html(text, level="info"):
    """返回内联状态徽章 HTML (success/warning/danger/info)"""
    safe_level = level if level in {"success", "warning", "danger", "info"} else "info"
    return f'<span class="badge badge-{safe_level}">{_html(text)}</span>'


def card_container(title, subtitle="", icon="", color="#38bdf8"):
    """
    高颜值卡片容器 — 用于页面的核心区块划分。
    支持标题、副标题、图标以及自动主题匹配。
    """
    title = _html(title)
    subtitle = _html(subtitle)
    icon = _html(icon)
    icon_html = (
        f'<span style="font-size:1.3rem; margin-right:8px;">{icon}</span>'
        if icon
        else ""
    )
    st.html(f"""
    <div style="margin-top: 24px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.06);">
        <div style="font-family: 'Outfit', sans-serif; font-size: 1.1rem; font-weight: 700; color: #f1f5f9; display: flex; align-items: center;">
            {icon_html}{title}
        </div>
        <div style="font-size: 0.82rem; color: #64748b; margin-top: 2px; margin-left: {"32" if icon else "0"}px;">
            {subtitle}
        </div>
    </div>
    """)
    return st.container()
