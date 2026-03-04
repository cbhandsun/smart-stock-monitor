import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os
import datetime
from modules.data_loader import fetch_trading_signals, fetch_research_reports, fetch_kline
from main import (
    get_market_overview, find_value_stocks, 
    find_momentum_stocks, find_growth_stocks,
    generate_ai_report, get_stock_names_batch
)

try:
    from modules.fundamentals import get_financial_health_score
    from modules.quant import calculate_metrics
except ImportError:
    pass

# ---- Configuration ----
WATCHLIST_FILE = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/watchlist.json"
REPORT_DIR = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/reports"

# ---- Theme & CSS ----
st.set_page_config(
    page_title="Smart Stock Monitor Pro",
    layout="wide",
    page_icon="🚀",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    /* Custom Styling */
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stock-card {
        border: 1px solid #e9ecef;
        padding: 20px;
        border-radius: 12px;
        background: white;
        margin-bottom: 20px;
    }
    div[data-testid="stExpander"] {
        border: none !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    /* Tab active styling */
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 1.1rem;
        font-weight: 600;
    }
    </style>
    """, unsafe_allow_html=True)

# ---- Data Helpers ----
def load_watchlist():
    try:
        if os.path.exists(WATCHLIST_FILE):
            with open(WATCHLIST_FILE, "r") as f:
                return json.load(f)
    except: pass
    return ["601318"]

def save_watchlist(stocks):
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(stocks, f)
    except: pass

def load_cached_report(symbol):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    path = f"{REPORT_DIR}/{date_str}/{symbol}.md"
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read(), True
    return None, False

# ---- Session State ----
if 'selected_stock' not in st.session_state:
    st.session_state['selected_stock'] = "601318"

# ---- Sidebar ----
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/bullish.png", width=80)
    st.title("SSM Pro v3.0")
    st.subheader("🛠️ 控制面板")
    
    with st.expander("📋 自选股管理", expanded=True):
        my_stocks = load_watchlist()
        name_map = get_stock_names_batch(my_stocks)
        
        c1, c2 = st.columns([3,1])
        add_code = c1.text_input("代码", placeholder="如 600519", label_visibility="collapsed")
        if c2.button("➕"):
            if add_code and add_code not in my_stocks:
                my_stocks.append(add_code)
                save_watchlist(my_stocks)
                st.rerun()
        
        if my_stocks:
            rem_list = st.multiselect("批量移除", my_stocks, format_func=lambda x: f"{x} {name_map.get(x, '')}")
            if rem_list and st.button("🗑️ 确认删除", type="secondary"):
                for x in rem_list: my_stocks.remove(x)
                save_watchlist(my_stocks)
                st.rerun()

    st.markdown("---")
    st.caption("🚀 Powered by Gemini & Sina Finance")

# ---- Main Layout ----
tab1, tab2 = st.tabs(["🎯 策略选股中心", "🧠 深度诊断工作台"])

with tab1:
    # 1. Market Overview Row
    ov = get_market_overview()
    if not ov.empty:
        cols = st.columns(len(ov))
        for i, row in enumerate(ov.itertuples()):
            color = "normal" if row.涨跌幅 == 0 else "inverse" if row.涨跌幅 < 0 else "normal"
            cols[i].metric(
                label=row.名称, 
                value=f"{row.最新价:,.2f}", 
                delta=f"{row.涨跌幅:+.2f}%",
                delta_color=color
            )
    
    st.markdown("### 🎯 智能策略引擎")
    strategy_cols = st.columns([1, 1, 1])
    
    # We use cards to explain strategies
    with strategy_cols[0]:
        st.info("**💎 价值挖掘**\n\n寻找 PE < 25 & PB < 2.5 的低估值优质标的。")
    with strategy_cols[1]:
        st.success("**🔥 趋势波段**\n\n捕获涨幅 1%~9% 且成交活跃的动能标的。")
    with strategy_cols[2]:
        st.warning("**🌟 成长之星**\n\n筛选成交额 > 1亿 且走势稳健的成长型企业。")

    strategy = st.radio("当前策略激活", ["价值挖掘", "趋势波段", "成长之星"], horizontal=True, label_visibility="collapsed")
    
    # Data Logic
    if strategy == "价值挖掘": df_display = find_value_stocks()
    elif strategy == "趋势波段": df_display = find_momentum_stocks()
    else: df_display = find_growth_stocks()

    if not df_display.empty:
        df_display.insert(0, "选择", False)
        st.markdown("---")
        edited_df = st.data_editor(
            df_display,
            hide_index=True,
            column_config={
                "选择": st.column_config.CheckboxColumn("📌", width="small"),
                "代码": st.column_config.TextColumn("代码", width="small"),
                "涨跌幅": st.column_config.NumberColumn("涨跌幅%", format="%.2f%%"),
                "最新价": st.column_config.NumberColumn("价格", format="¥%.2f")
            },
            disabled=[c for c in df_display.columns if c != "选择"],
            use_container_width=True
        )
        
        selected_rows = edited_df[edited_df["选择"] == True]
        if not selected_rows.empty:
            btn_cols = st.columns([1, 1, 4])
            if btn_cols[0].button("⭐ 批量加自选", use_container_width=True):
                added = [c for c in selected_rows['代码'] if c not in my_stocks]
                if added:
                    my_stocks.extend(added)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ 已成功添加 {len(added)} 只股票")
                    st.rerun()
            if btn_cols[1].button("🔍 诊断所选", use_container_width=True, type="primary"):
                st.session_state['selected_stock'] = selected_rows.iloc[0]['代码']
                st.toast("⚡ 已定位至诊断工作台")
    else:
        st.empty()

with tab2:
    # Diagnostic Sync
    cur_stock = st.session_state['selected_stock']
    if cur_stock not in my_stocks: my_stocks.insert(0, cur_stock)
    
    # Top Control Bar
    c1, c2, c3 = st.columns([3, 2, 2])
    sel_stock = c1.selectbox(
        "选择股票对象", 
        my_stocks, 
        index=my_stocks.index(cur_stock) if cur_stock in my_stocks else 0,
        format_func=lambda x: f"🔍 {x} {name_map.get(x, '')}"
    )
    st.session_state['selected_stock'] = sel_stock
    
    # Action Row
    cached_report, is_cached = load_cached_report(sel_stock)
    refresh_btn = c2.button("🚀 启动 AI 全量诊断", use_container_width=True, type="primary")
    
    # Financial Row
    st.markdown("---")
    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    kline = fetch_kline("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock)
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}
    
    mc1, mc2, mc3, mc4 = st.columns(4)
    if f_data:
        mc1.metric("财务健康分", f"{f_data.get('score')}/100")
    if q_metrics:
        mc2.metric("RSI (14)", f"{q_metrics.get('rsi'):.1f}")
        mc3.metric("年化波动率", f"{q_metrics.get('volatility_ann'):.1f}%")
        mc4.metric("布林位置", "中轨上方" if q_metrics.get('rsi',50) > 50 else "中轨下方")

    # Content Area
    col_chart, col_ai = st.columns([3, 2])
    
    with col_chart:
        if not kline.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=kline['日期'], open=kline['开盘'], high=kline['最高'], 
                low=kline['最低'], close=kline['收盘'],
                increasing_line_color= '#ef5350', decreasing_line_color= '#26a69a'
            )])
            fig.update_layout(
                height=500, margin=dict(l=0,r=0,t=10,b=0),
                xaxis_rangeslider_visible=False,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_ai:
        if refresh_btn:
            formatted = "sh" + sel_stock if sel_stock.startswith('6') else "sz" + sel_stock
            with st.spinner("🧠 Gemini 正在深度研判中..."):
                sig = fetch_trading_signals(formatted)
                rep = fetch_research_reports(sel_stock)
                sname = name_map.get(sel_stock, sel_stock)
                report_text = generate_ai_report(sel_stock, sname, rep, sig)
                st.markdown(report_text)
                # Auto-cache
                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f:
                    f.write(report_text)
        elif is_cached:
            st.markdown(cached_report)
        else:
            st.info("💡 点击上方按钮生成 AI 诊断报告")

st.divider()
st.caption(f"Smart Stock Monitor Pro v3.0 | 运行环境: {'Proxy 10808' if 'HTTP_PROXY' in os.environ else 'Direct'}")
