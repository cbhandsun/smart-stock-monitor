"""
大盘指数条渲染 — market 子包 v2.1
CSS 已移至 static/style.css（消除 Streamlit 内联 <style> 渲染问题）
"""
import streamlit as st
from datetime import datetime


def _render_market_bar():
    """精品大盘指数条 — 动态色彩 + LIVE 闪烁 + 风控警报"""
    from main import get_market_overview
    ov = get_market_overview()
    if ov.empty:
        return

    items_html = ""
    for _, r in ov.iterrows():
        chg = float(r.get('涨跌幅', 0))
        price = float(r.get('最新价', 0))
        name = r["名称"]

        if chg > 0:
            clr = "#f43f5e"
            bg  = "rgba(244,63,94,0.08)"
            brd = "#f43f5e22"
            icon = "▲"
        elif chg < 0:
            clr = "#10b981"
            bg  = "rgba(16,185,129,0.08)"
            brd = "#10b98122"
            icon = "▼"
        else:
            clr = "#64748b"
            bg  = "rgba(100,116,139,0.06)"
            brd = "#64748b22"
            icon = "━"

        items_html += (
            f'<span class="mbar-item" style="background:{bg};border:1px solid {brd};">'
            f'<span class="mbar-name">{name}</span>'
            f'<span class="mbar-price">{price:,.2f}</span>'
            f'<span class="mbar-chg" style="color:{clr};">{icon}{abs(chg):.2f}%</span>'
            f'</span>'
        )

    now_str = datetime.now().strftime("%H:%M")

    # 纯 HTML，无内联 <style>（CSS 在 static/style.css）
    bar_html = (
        f'<div class="market-bar-v2">'
        f'<span class="mbar-live">LIVE</span>'
        f'{items_html}'
        f'<span class="mbar-time">{now_str}</span>'
        f'</div>'
    )
    st.html(bar_html)

    # 风控警报 — 使用 CSS class 而非内联样式
    avg_drop = ov['涨跌幅'].mean()
    if avg_drop <= -2.0:
        st.markdown(
            f'<div class="risk-alert-high">'
            f'⚠️ <strong>智能风控警报</strong>：三大指数均跌 {avg_drop:.2f}%，'
            f'建议多头仓位降至 30% 以下，关注黄金 ETF (518880) 等避险资产。'
            f'</div>',
            unsafe_allow_html=True
        )
    elif avg_drop <= -1.0:
        st.markdown(
            f'<div class="risk-alert-mid">'
            f'🛡️ <strong>风控提示</strong>：大盘均跌 {avg_drop:.2f}%，'
            f'建议停止加仓，清理弱势标的。'
            f'</div>',
            unsafe_allow_html=True
        )
