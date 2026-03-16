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
    new_val = st.text_input(label, value=current, key=f"stock_sel_{key_suffix}")

    # 同步回 session_state
    if new_val and new_val != current:
        st.session_state['selected_stock'] = new_val

    return new_val


def nav_to_page(target_page, label, icon="→", stock_code=None, button_type="secondary"):
    """
    跨页面导航按钮。
    点击后跳转到目标页面，可选地设置分析标的。
    """
    if st.button(f"{icon} {label}", key=f"nav_{target_page}_{id(nav_to_page)}", 
                 type=button_type, use_container_width=True):
        if stock_code:
            st.session_state['selected_stock'] = stock_code
        st.session_state['current_page'] = target_page
        st.rerun()

