"""
📡 市场信号流 + 个股深度分析页面
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os
import datetime

from modules.data_loader import fetch_trading_signals, fetch_research_reports, fetch_kline
from main import (
    get_market_overview, find_value_stocks,
    find_momentum_stocks, find_growth_stocks,
    generate_ai_report, get_stock_names_batch
)
from pages import load_watchlist, save_watchlist, load_cached_report, REPORT_DIR

# 条件导入
try:
    from modules.fundamentals import get_financial_health_score
    from modules.quant import calculate_metrics, calculate_all_indicators
    from utils.charts import create_candlestick_chart
except ImportError:
    get_financial_health_score = None
    calculate_metrics = None
    calculate_all_indicators = None
    create_candlestick_chart = None


def _create_indicator_chart(data, name, theme="dark"):
    """创建技术指标副图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    fig = go.Figure()

    if name == 'MACD':
        fig.add_trace(go.Bar(
            x=data['日期'], y=data['MACD_Hist'], name='Histogram',
            marker_color=['#ef4444' if v < 0 else '#10b981' for v in data['MACD_Hist']]
        ))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['MACD'], name='MACD', line=dict(color='#3b82f6')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['MACD_Signal'], name='Signal', line=dict(color='#f59e0b')))
    elif name == 'KDJ':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_K'], name='K', line=dict(color='#3b82f6')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_D'], name='D', line=dict(color='#f59e0b')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_J'], name='J', line=dict(color='#ec4899')))
        fig.add_hline(y=80, line_dash="dash", line_color="red")
        fig.add_hline(y=20, line_dash="dash", line_color="green")
    elif name == 'RSI':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['RSI'], name='RSI', line=dict(color='#3b82f6', fill='tozeroy')))
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超买")
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超卖")
    elif name == 'CCI':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['CCI'], name='CCI', line=dict(color='#8b5cf6')))
        fig.add_hline(y=100, line_dash="dash", line_color="red")
        fig.add_hline(y=-100, line_dash="dash", line_color="green")

    fig.update_layout(
        template=template, height=200,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=10))
    )
    return fig


def render(L, my_stocks, name_map):
    """渲染市场页面"""
    # 移除重复的 header

    # Market Overview
    c1, c2 = st.columns([8, 1])
    with c1:
        st.markdown(f"## 📡 {L['market_discovery']}")
    with c2:
        if st.button("🔄 刷新", key="refresh_market", use_container_width=True):
            st.cache_data.clear()
            st.toast("市场行情已刷新", icon="📈")
            st.rerun()

    ov = get_market_overview()
    if not ov.empty:
        cols = st.columns(len(ov))
        for i, r in enumerate(ov.itertuples()):
            delta_color = "normal" if r.涨跌幅 >= 0 else "inverse"
            cols[i].metric(r.名称, f"{r.最新价:,.1f}", f"{r.涨跌幅:+.2f}%", delta_color=delta_color)

        # 🚨 Smart Risk Control AI Agent
        avg_drop = ov['涨跌幅'].mean()
        if avg_drop <= -2.0:
            st.error(f"**⚠️ 智能风控警报 (极端风险)：** 当前三大指数平均跌幅达到 `{avg_drop:.2f}%`，系统判定 Beta 风险溢出。 \n\n"
                     f"**🤖 AI 对冲建议：** \n"
                     f"- 建议将组合多头仓位降至 30% 以下，或利用期权/股指期货 (IF/IC) 进行套期保值。\n"
                     f"- 避险资产配置：近期可关注黄金相关 ETF (如 `518880`) 作为流动性缓冲。")
        elif avg_drop <= -1.0:
            st.warning(f"**🛡️ 智能风控提示 (系统性承压)：** 当前大盘平均跌幅 `{avg_drop:.2f}%`。建议停止加仓，清理组合中处于下降通道的弱势标的。")

    # Strategy Capture
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"### 🎯 {L['strat_capture']}")
    
    if 'capture_strat' not in st.session_state:
        st.session_state['capture_strat'] = 'Value'

    # Injecting CSS specifically for the Strategy buttons by using nth-of-type(1) under the strat section
    st.markdown("""
    <style>
    .strat-btn-container {
        display: none;
    }
    
    /* Target the Horizontal Block immediately following our h3 */
    h3:contains("🎯") ~ div[data-testid="stHorizontalBlock"]:first-of-type button {
        height: 65px;
        border-radius: 12px;
        font-size: 1.1rem;
        font-weight: 600;
        font-family: 'Outfit', sans-serif;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    h3:contains("🎯") ~ div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="column"]:nth-of-type(1) button {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%) !important;
        border-left: 4px solid #3b82f6 !important;
    }
    h3:contains("🎯") ~ div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="column"]:nth-of-type(1) button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, rgba(30, 58, 138, 0.9) 0%, rgba(15, 23, 42, 1) 100%) !important;
        box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3) !important;
    }

    h3:contains("🎯") ~ div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="column"]:nth-of-type(2) button {
        background: linear-gradient(135deg, rgba(6, 78, 59, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%) !important;
        border-left: 4px solid #10b981 !important;
    }
    h3:contains("🎯") ~ div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="column"]:nth-of-type(2) button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, rgba(6, 78, 59, 0.9) 0%, rgba(15, 23, 42, 1) 100%) !important;
        box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3) !important;
    }

    h3:contains("🎯") ~ div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="column"]:nth-of-type(3) button {
        background: linear-gradient(135deg, rgba(120, 53, 15, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%) !important;
        border-left: 4px solid #f59e0b !important;
    }
    h3:contains("🎯") ~ div[data-testid="stHorizontalBlock"]:first-of-type div[data-testid="column"]:nth-of-type(3) button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, rgba(120, 53, 15, 0.9) 0%, rgba(15, 23, 42, 1) 100%) !important;
        box-shadow: 0 4px 15px rgba(245, 158, 11, 0.3) !important;
    }
    </style>
    """, unsafe_allow_html=True)

    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        if st.button("💎 Value Discovery", use_container_width=True, type="primary" if st.session_state['capture_strat'] == 'Value' else "secondary"):
            st.session_state['capture_strat'] = 'Value'
            st.rerun()
    with sc2:
        if st.button("🔥 Momentum Max", use_container_width=True, type="primary" if st.session_state['capture_strat'] == 'Momentum' else "secondary"):
            st.session_state['capture_strat'] = 'Momentum'
            st.rerun()
    with sc3:
        if st.button("🌟 Growth Star", use_container_width=True, type="primary" if st.session_state['capture_strat'] == 'Growth' else "secondary"):
            st.session_state['capture_strat'] = 'Growth'
            st.rerun()

    df = find_value_stocks() if st.session_state['capture_strat'] == "Value" else find_momentum_stocks() if st.session_state['capture_strat'] == "Momentum" else find_growth_stocks()

    if not df.empty:
        df.insert(0, "📌", False)
        
        col_cfg = {
            "📌": st.column_config.CheckboxColumn("选择", default=False),
            "代码": st.column_config.TextColumn("代码", width="small"),
            "名称": st.column_config.TextColumn("名称", width="medium"),
            "最新价": st.column_config.NumberColumn("最新价", format="¥ %.2f"),
            "涨跌幅": st.column_config.NumberColumn("涨跌幅%", format="%.2f%%"),
        }
        
        if "PE" in df.columns:
            col_cfg["PE"] = st.column_config.ProgressColumn("PE (市盈率)", format="%.1f", min_value=0, max_value=50)
            col_cfg["PB"] = st.column_config.ProgressColumn("PB (市净率)", format="%.2f", min_value=0, max_value=5)
            disabled_cols = ["代码", "名称", "最新价", "涨跌幅", "PE", "PB"]
        elif "成交额" in df.columns:
            col_cfg["成交额"] = st.column_config.NumberColumn("成交额", format="¥ %d")
            disabled_cols = ["代码", "名称", "最新价", "涨跌幅", "成交额"]
        else:
            disabled_cols = ["代码", "名称", "最新价", "涨跌幅"]

        res = st.data_editor(
            df, hide_index=True, use_container_width=True,
            column_config=col_cfg,
            disabled=disabled_cols,
        )
        sel = res[res["📌"] == True]
        if not sel.empty:
            if st.button("Sync to Workspace", type="primary", use_container_width=True):
                added = [c for c in sel['代码'] if c not in my_stocks]
                my_stocks.extend(added)
                save_watchlist(my_stocks)
                st.toast(f"✅ 已添加 {len(added)} 只股票", icon="🎯")
                st.balloons()
                st.rerun()

    # Stock Analysis Section
    from components.dna_analyzer import render_dna_analyzer
    render_dna_analyzer(L, my_stocks, name_map)
