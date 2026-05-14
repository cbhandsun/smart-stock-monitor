"""
HTML 渲染工具 — SSM Quantum Pro
解决 st.markdown(unsafe_allow_html=True) 解析复杂 HTML 时出现原始文本的问题

根本原因：
  st.markdown() 先经过 Markdown 解析器，复杂嵌套 HTML 会被部分转义
  st.html()     直接注入 DOM，完全绕过 Markdown 解析，100% 可靠

使用规则：
  ✅ st.html(html)          → 渲染复杂 HTML 卡片、表格、自定义组件
  ✅ st.markdown(text)      → 渲染普通 Markdown 文本（无 HTML）
  ✅ st.markdown(css_only)  → 只含 <style> 标签时仍可用（从 style.css 加载更好）
  ❌ st.markdown(complex_html, unsafe_allow_html=True) → 禁止用于复杂 HTML
"""
import streamlit as st


def render_html(html: str) -> None:
    """
    安全渲染任意复杂 HTML。
    优先使用 st.html()（Streamlit 1.31+），降级到 st.markdown()。
    """
    try:
        st.html(html)
    except AttributeError:
        # Streamlit < 1.31 降级方案
        st.markdown(html, unsafe_allow_html=True)


def render_card(html: str) -> None:
    """渲染一张 HTML 卡片（语义化别名）"""
    render_html(html)


def render_metric_html(html: str) -> None:
    """渲染指标/统计 HTML 块"""
    render_html(html)


def inject_css(css: str) -> None:
    """
    注入 CSS 样式（推荐从 style.css 加载，此函数作为补丁入口）
    仅包含 <style> 标签时，st.markdown 是安全的
    """
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
