"""
统一的 UI 组件：页面头部、全局标的指示器、股票选择器、跨页导航
"""
import streamlit as st


def page_header(title, subtitle="", icon=""):
    """统一的页面头部组件"""
    sub_html = f"<span style='color:#64748b; font-size:0.85rem; margin-left:12px;'>{subtitle}</span>" if subtitle else ""
    st.markdown(f"""
<div style="margin-bottom: 16px;">
    <div style="font-family: 'Outfit', sans-serif; font-size: 1.5rem; font-weight: 700; color: #f1f5f9;">
        {icon} {title}{sub_html}
    </div>
</div>
""", unsafe_allow_html=True)


def stock_context_bar(name_map):
    """全局标的指示器 — 始终显示当前分析的股票"""
    current = st.session_state.get('selected_stock', '601318')
    cur_name = name_map.get(current, '')

    st.markdown(f"""
<div style="background: rgba(30,41,59,0.35); border: 1px solid rgba(255,255,255,0.05);
     border-radius: 10px; padding: 6px 16px; margin-bottom: 12px;
     display: flex; align-items: center; gap: 10px; font-size: 0.82rem;">
    <span style="color: #64748b;">当前标的</span>
    <span style="color: #38bdf8; font-weight: 600;">{current}</span>
    <span style="color: #94a3b8;">{cur_name}</span>
</div>
""", unsafe_allow_html=True)


def stock_selector(label="分析标的", key_suffix="default"):
    """
    统一的股票代码选择器。
    修改后自动同步到 session_state['selected_stock']。
    返回: 当前选中的股票代码字符串
    """
    current = st.session_state.get('selected_stock', '601318')
    new_val = st.text_input(label, value=current, key=f"PRO_SSM_V7_stock_sel_{key_suffix}")

    # 同步回 session_state
    if new_val and new_val != current:
        st.session_state['selected_stock'] = new_val

    return new_val


def nav_to_page(target_page, label, icon="→", stock_code=None, button_type="secondary", key_suffix=""):
    """
    跨页面导航按钮。
    点击后跳转到目标页面，可选地设置分析标的。
    """
    # 使用 PRO_SSM_V7_ 命名空间前缀
    clean_label = "".join(filter(str.isalnum, label))
    btn_key = f"PRO_SSM_V7_nav_{target_page}_{clean_label}_{key_suffix}"
    if st.button(f"{icon} {label}", key=btn_key,
                 type=button_type, use_container_width=True):
        if stock_code:
            st.session_state['selected_stock'] = stock_code
        st.session_state['current_page'] = target_page
        st.rerun()


def info_card(title, value, subtitle="", icon="", color="#38bdf8"):
    """Glassmorphism 信息卡片 — 利用 CSS .ssm-card 样式"""
    icon_html = f'<span style="font-size:1.4rem; margin-right:8px;">{icon}</span>' if icon else ''
    sub_html = f'<div class="ssm-card-sub">{subtitle}</div>' if subtitle else ''
    st.markdown(f'''<div class="ssm-card">
    <div class="ssm-card-title">{icon_html}{title}</div>
    <div class="ssm-card-value" style="color:{color};">{value}</div>
    {sub_html}
</div>''', unsafe_allow_html=True)


def empty_state(icon="📋", title="暂无数据", description="", action_label=None, action_key=None):
    """空状态占位面板 — 居中图标 + 说明文字 + 可选操作按钮"""
    st.markdown(f'''<div class="empty-state">
    <div class="empty-state-icon">{icon}</div>
    <div class="empty-state-title">{title}</div>
    <div class="empty-state-desc">{description}</div>
</div>''', unsafe_allow_html=True)
    if action_label and action_key:
        _, center, _ = st.columns([2, 1, 2])
        with center:
            final_key = f"PRO_SSM_V7_empty_{action_key}"
            return st.button(action_label, key=final_key, type="primary", use_container_width=True)
    return False


def status_badge_html(text, level="info"):
    """返回内联状态徽章 HTML (success/warning/danger/info)"""
    return f'<span class="badge badge-{level}">{text}</span>'


def card_container(title, subtitle="", icon="", color="#38bdf8"):
    """
    高颜值卡片容器 — 用于页面的核心区块划分。
    支持标题、副标题、图标以及自动主题匹配。
    """
    import streamlit as st
    icon_html = f'<span style="font-size:1.3rem; margin-right:8px;">{icon}</span>' if icon else ''
    st.markdown(f"""
    <div style="margin-top: 24px; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.06);">
        <div style="font-family: 'Outfit', sans-serif; font-size: 1.1rem; font-weight: 700; color: #f1f5f9; display: flex; align-items: center;">
            {icon_html}{title}
        </div>
        <div style="font-size: 0.82rem; color: #64748b; margin-top: 2px; margin-left: { '32' if icon else '0' }px;">
            {subtitle}
        </div>
    </div>
    """, unsafe_allow_html=True)
    return st.container()

