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

# ---- Theme & CSS Premium ----
st.set_page_config(
    page_title="SSM Pro Intelligence",
    layout="wide",
    page_icon="💎",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    .main {
        background-color: #f4f7f6;
    }
    
    /* Premium Metric Card */
    div[data-testid="stMetric"] {
        background: white;
        padding: 18px !important;
        border-radius: 12px;
        border: 1px solid #edf2f7;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        transition: transform 0.2s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }
    
    /* Strategy Selection Card */
    .strategy-card {
        background: white;
        padding: 1.5rem;
        border-radius: 15px;
        border-left: 5px solid #3182ce;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    /* Custom Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1a202c;
        color: white;
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #e2e8f0;
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        border-bottom: 2px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent !important;
        border: none !important;
        color: #718096 !important;
        font-weight: 600 !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: #3182ce !important;
        border-bottom: 2px solid #3182ce !important;
    }
    
    /* Status Tags */
    .status-tag {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
        font-weight: bold;
        text-transform: uppercase;
    }
    .tag-bull { background-color: #c6f6d5; color: #22543d; }
    .tag-bear { background-color: #fed7d7; color: #822727; }
    
    /* AI Report Text */
    .ai-report-container {
        line-height: 1.6;
        color: #2d3748;
        font-size: 1.05rem;
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

# ---- Sidebar Premium ----
with st.sidebar:
    st.markdown("<h1 style='color: #63b3ed; font-size: 1.8rem; margin-bottom: 0;'>SSM PRO</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #a0aec0; font-size: 0.9rem; margin-top: 0;'>Intelligence Terminal v3.1</p>", unsafe_allow_html=True)
    
    st.markdown("---")
    
    with st.expander("⭐ 自选股监控", expanded=True):
        my_stocks = load_watchlist()
        name_map = get_stock_names_batch(my_stocks)
        
        # Cleaner list with icons
        for stock in my_stocks:
            sc1, sc2 = st.columns([4, 1])
            sc1.markdown(f"**{stock}** `{name_map.get(stock, '...')}`")
            if sc2.button("×", key=f"del_{stock}", help="移出自选"):
                my_stocks.remove(stock)
                save_watchlist(my_stocks)
                st.rerun()

    with st.expander("➕ 添加股票", expanded=False):
        add_code = st.text_input("输入股票代码", key="sidebar_add")
        if st.button("添加", use_container_width=True):
            if add_code and add_code not in my_stocks:
                my_stocks.append(add_code)
                save_watchlist(my_stocks)
                st.rerun()

    st.markdown("---")
    # Quick Health Check
    st.markdown("🌐 **系统状态**")
    st.success("核心引擎: 运行中")
    st.info(f"数据源: {'代理中转' if 'HTTP_PROXY' in os.environ else '直连模式'}")

# ---- Main Layout Premium ----
tab1, tab2 = st.tabs(["📡 智能捕获终端", "🛡️ 深度研判中心"])

with tab1:
    # 1. High Performance Indices
    ov = get_market_overview()
    if not ov.empty:
        cols = st.columns(len(ov))
        for i, row in enumerate(ov.itertuples()):
            cols[i].metric(
                label=f"Index: {row.名称}", 
                value=f"{row.最新价:,.1f}", 
                delta=f"{row.涨跌幅:+.2f}%"
            )
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. Advanced Strategy Selection
    st.markdown("### 📡 策略信号捕获")
    s_col1, s_col2, s_col3 = st.columns(3)
    
    with s_col1:
        st.markdown("""<div class='strategy-card' style='border-left-color: #3182ce'>
            <h4 style='margin:0'>💎 价值深挖</h4>
            <p style='font-size: 0.85rem; color: #4a5568;'>高ROE & 低PE 优质龙头</p>
            </div>""", unsafe_allow_html=True)
    with s_col2:
        st.markdown("""<div class='strategy-card' style='border-left-color: #38a169'>
            <h4 style='margin:0'>🔥 强力动能</h4>
            <p style='font-size: 0.85rem; color: #4a5568;'>趋势突破 & 换手率激增</p>
            </div>""", unsafe_allow_html=True)
    with s_col3:
        st.markdown("""<div class='strategy-card' style='border-left-color: #d69e2e'>
            <h4 style='margin:0'>🌟 稳健成长</h4>
            <p style='font-size: 0.85rem; color: #4a5568;'>核心资产 & 持续盈利</p>
            </div>""", unsafe_allow_html=True)

    strategy_map = {"价值挖掘": "价值挖掘", "趋势波段": "趋势波段", "成长之星": "成长之星"}
    sel_strat = st.radio("选择策略源", ["价值挖掘", "趋势波段", "成长之星"], horizontal=True, label_visibility="collapsed")
    
    # Data Engine Integration
    if sel_strat == "价值挖掘": df_display = find_value_stocks()
    elif sel_strat == "趋势波段": df_display = find_momentum_stocks()
    else: df_display = find_growth_stocks()

    if not df_display.empty:
        df_display.insert(0, "📌", False)
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Interactive Grid
        event = st.data_editor(
            df_display,
            hide_index=True,
            column_config={
                "📌": st.column_config.CheckboxColumn(width="small"),
                "代码": st.column_config.TextColumn(width="small"),
                "涨跌幅": st.column_config.NumberColumn(format="%.2f%%"),
                "最新价": st.column_config.NumberColumn(format="¥%.2f")
            },
            disabled=[c for c in df_display.columns if c != "📌"],
            use_container_width=True
        )
        
        sel_list = event[event["📌"] == True]
        if not sel_list.empty:
            bc1, bc2 = st.columns([1, 4])
            if bc1.button("⭐ 追踪选中标的", type="primary", use_container_width=True):
                added = [c for c in sel_list['代码'] if c not in my_stocks]
                if added:
                    my_stocks.extend(added)
                    save_watchlist(my_stocks)
                    st.toast(f"✅ 已开始追踪 {len(added)} 个新标的", icon="🚀")
                    st.rerun()
            
            # Auto-jump tip
            if len(sel_list) == 1:
                st.session_state['selected_stock'] = sel_list.iloc[0]['代码']
                st.info(f"已锁定标的: {st.session_state['selected_stock']}，切换至[深度研判中心]即可查看")

with tab2:
    # 3. Decision Center Setup
    cur_stock = st.session_state['selected_stock']
    if cur_stock not in my_stocks: my_stocks.insert(0, cur_stock)
    
    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        sel_stock = st.selectbox(
            "研判对象", 
            my_stocks, 
            index=my_stocks.index(cur_stock) if cur_stock in my_stocks else 0,
            format_func=lambda x: f"🔍 {x} {name_map.get(x, '')}",
            label_visibility="collapsed"
        )
        st.session_state['selected_stock'] = sel_stock
    
    # Diagnostic Engine
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Financial DNA Stats
    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    kline = fetch_kline("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock)
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}
    
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        score = f_data.get('score', 0) if f_data else 50
        st.metric("核心财务评分", f"{score} / 100", delta="健康" if score > 60 else "关注")
    with m2:
        rsi = q_metrics.get('rsi', 0)
        st.metric("RSI (14)", f"{rsi:.1f}", delta="超买" if rsi > 70 else "超卖" if rsi < 30 else "常态", delta_color="inverse" if rsi > 70 else "normal")
    with m3:
        vol = q_metrics.get('volatility_ann', 0)
        st.metric("年化波动率", f"{vol:.1f}%", delta="高波" if vol > 40 else "低平")
    with m4:
        st.metric("研判结论", "建议增持" if rsi < 40 and score > 70 else "建议观察", delta="AI 实时判定")

    # Interactive Chart & Intelligence
    chart_tab, ai_tab = st.columns([3, 2])
    
    with chart_tab:
        if not kline.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=kline['日期'], open=kline['开盘'], high=kline['最高'], 
                low=kline['最低'], close=kline['收盘'],
                increasing_line_color= '#ef5350', decreasing_line_color= '#26a69a'
            )])
            fig.update_layout(
                height=450, margin=dict(l=0,r=0,t=0,b=0),
                xaxis_rangeslider_visible=False,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with ai_tab:
        cached_report, is_cached = load_cached_report(sel_stock)
        
        btn_area = st.container()
        if btn_area.button("🚀 启动 Gemini AI 深度穿透", type="primary", use_container_width=True):
            formatted = "sh" + sel_stock if sel_stock.startswith('6') else "sz" + sel_stock
            with st.spinner("⏳ 正连接研报数据库并进行多维推理..."):
                sig = fetch_trading_signals(formatted)
                rep = fetch_research_reports(sel_stock)
                sname = name_map.get(sel_stock, sel_stock)
                report_text = generate_ai_report(sel_stock, sname, rep, sig)
                st.markdown(f"<div class='ai-report-container'>{report_text}</div>", unsafe_allow_html=True)
                # Save
                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f:
                    f.write(report_text)
        elif is_cached:
            st.markdown(f"<div class='ai-report-container'>{cached_report}</div>", unsafe_allow_html=True)
        else:
            st.info("👈 选择标的并点击按钮启动 AI 深度诊断")

st.markdown("<br><br>", unsafe_allow_html=True)
st.divider()
st.markdown("<p style='text-align: center; color: #a0aec0; font-size: 0.8rem;'>SSM Pro Intelligence Terminal | 2026 Powered by Gemini 1.5 Pro & Sina Finance API</p>", unsafe_allow_html=True)
