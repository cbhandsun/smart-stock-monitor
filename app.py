import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os
import requests
import datetime
from modules.data_loader import fetch_trading_signals, fetch_research_reports, fetch_kline
from main import (
    get_market_overview, get_hot_trend_stocks, find_value_stocks, 
    find_momentum_stocks, find_growth_stocks,
    generate_ai_report, get_stock_names_batch
)

try:
    from modules.macro import get_macro_indicators
    from modules.fundamentals import get_financial_health_score
    from modules.quant import calculate_metrics
except ImportError:
    pass

WATCHLIST_FILE = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/watchlist.json"
REPORT_DIR = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/reports"

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

st.set_page_config(page_title="Smart Stock Monitor Pro", layout="wide", page_icon="🚀")

# ---- Sidebar ----
with st.sidebar:
    st.title("⚙️ 智能投研配置")
    st.markdown("### 📋 自选股管理")
    my_stocks = load_watchlist()
    name_map = get_stock_names_batch(my_stocks)
    def format_stock(opt): 
        n = name_map.get(opt, '')
        return f"{opt} | {n}" if n else opt

    c1, c2 = st.columns([2,1])
    add_code = c1.text_input("加自选", placeholder="代码", label_visibility="collapsed")
    if c2.button("➕"):
        if add_code and add_code not in my_stocks:
            my_stocks.append(add_code)
            save_watchlist(my_stocks)
            st.rerun()
            
    if my_stocks:
        rem_list = st.multiselect("移除", my_stocks, format_func=format_stock)
        if rem_list and st.button("🗑️"):
            for x in rem_list: my_stocks.remove(x)
            save_watchlist(my_stocks)
            st.rerun()
            
    st.markdown("---")
    st.markdown("### 🇨🇳 A股宏观风向标")
    if get_macro_indicators:
        if 'macro_data' not in st.session_state:
            st.session_state['macro_data'] = get_macro_indicators()
        macro = st.session_state['macro_data']
        a50 = macro.get('富时中国A50', {})
        st.metric("A50期货", f"{a50.get('price',0):.1f}", f"{a50.get('change_pct',0):.2f}%")
        cnh = macro.get('USD/CNH', {})
        st.metric("离岸人民币", f"{cnh.get('price',0):.4f}")

# ---- Main ----
st.title("🚀 Smart Stock Monitor Pro v2.2")
tab1, tab2 = st.tabs(["📊 策略选股中心", "🧠 个股深度诊断"])

with tab1:
    st.header("📈 今日大盘趋势")
    try:
        ov = get_market_overview()
        if not ov.empty:
            cols = st.columns(len(ov))
            for i, row in enumerate(ov.itertuples()):
                cols[i].metric(row.名称, f"{row.最新价}", f"{row.涨跌幅}%")
    except: st.warning("数据加载中...")
    
    st.divider()
    st.header("🎯 智能选股策略库")
    strategy = st.radio("选择选股逻辑", ["价值挖掘 (低估值)", "趋势波段 (强动能)", "成长之星 (大蓝筹)"], horizontal=True)
    
    if strategy == "价值挖掘 (低估值)":
        st.subheader("💎 价值挖掘：低 PE / 低 PB 标的")
        df_val = find_value_stocks()
        st.dataframe(df_val, use_container_width=True)
    elif strategy == "趋势波段 (强动能)":
        st.subheader("🔥 趋势波段：近期涨幅稳健 + 成交活跃")
        df_mom = find_momentum_stocks()
        st.dataframe(df_mom, use_container_width=True)
    else:
        st.subheader("🌟 成长之星：高权重大市值 + 稳健走势")
        df_gro = find_growth_stocks()
        st.dataframe(df_gro, use_container_width=True)

with tab2:
    st.header("🔍 深度诊断工作台")
    sel_stock = st.selectbox("选择自选股", my_stocks, format_func=format_stock)
    cached_report, is_cached = load_cached_report(sel_stock)
    
    col_btn, col_info = st.columns([1, 3])
    do_gen = col_btn.button("🚀 生成/刷新诊断", type="primary")
    
    if is_cached and not do_gen:
        st.info(f"📅 加载今日缓存报告 ({datetime.datetime.now().strftime('%Y-%m-%d')})")
        st.markdown(cached_report)
    elif do_gen:
        formatted = "sh" + sel_stock if sel_stock.startswith('6') else "sz" + sel_stock
        with st.spinner("AI 正在实时分析..."):
            sig = fetch_trading_signals(formatted)
            rep = fetch_research_reports(sel_stock)
            sname = name_map.get(sel_stock, sel_stock)
            report_text = generate_ai_report(sel_stock, sname, rep, sig)
            st.success(report_text)
            d_str = datetime.datetime.now().strftime("%Y-%m-%d")
            os.makedirs(f"{REPORT_DIR}/{d_str}", exist_ok=True)
            with open(f"{REPORT_DIR}/{d_str}/{sel_stock}.md", "w") as f:
                f.write(report_text)
    else: st.info("请选择股票并点击生成报告")

    st.markdown("---")
    st.subheader("📊 数据透视")
    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    kline = fetch_kline("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock)
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}
    
    c1, c2 = st.columns([2, 1])
    with c1:
        if not kline.empty:
            fig = go.Figure(data=[go.Candlestick(x=kline['日期'], open=kline['开盘'], high=kline['最高'], low=kline['最低'], close=kline['收盘'])])
            fig.update_layout(height=350, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        if f_data:
            st.metric("财务评分", f"{f_data.get('score')}")
            st.progress(f_data.get('score'))
        if q_metrics:
            st.metric("RSI (14)", f"{q_metrics.get('rsi'):.1f}")
            st.metric("年化波动率", f"{q_metrics.get('volatility_ann'):.1f}%")

st.divider()
st.caption("Smart Stock Monitor Pro v2.2 | Powered by Gemini & Sina Finance")
