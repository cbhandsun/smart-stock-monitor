"""
统一的 UI 组件：页面头部、全局标的指示器等
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
