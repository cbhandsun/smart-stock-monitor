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

# ---- Theme & Neumorphic Design ----
st.set_page_config(
    page_title="SSM Terminal Excellence",
    layout="wide",
    page_icon="💠",
    initial_sidebar_state="expanded"
)

# Custom Glassmorphism & Modern UI CSS
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700&family=JetBrains+Mono&display=swap');
    
    :root {
        --primary: #3b82f6;
        --bg-main: #fcfdfe;
        --card-bg: rgba(255, 255, 255, 0.8);
        --glass-border: rgba(226, 232, 240, 0.6);
    }

    html, body, [class*="css"] {
        font-family: 'Sora', sans-serif;
        color: #1e293b;
    }

    .main {
        background: radial-gradient(circle at top left, #f1f5f9, #ffffff);
    }

    /* Glassmorphism Cards */
    div[data-testid="stMetric"] {
        background: var(--card-bg) !important;
        backdrop-filter: blur(10px);
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05) !important;
    }

    /* Sidebar - Modern Dark Mode */
    [data-testid="stSidebar"] {
        background: #0f172a !important;
        border-right: 1px solid #1e293b;
    }
    
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p {
        color: #f8fafc !important;
    }

    /* Tab Modernization */
    .stTabs [data-baseweb="tab-list"] {
        background: #f1f5f9;
        padding: 8px;
        border-radius: 12px;
        display: inline-flex;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        padding: 8px 24px !important;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: white !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        color: var(--primary) !important;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }

    /* Data Editor Enhancement */
    div[data-testid="stDataEditor"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }

    /* AI Report Style */
    .ai-bubble {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        line-height: 1.8;
        font-size: 1rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.04);
    }
    
    .code-font {
        font-family: 'JetBrains Mono', monospace;
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

# ---- Sidebar Modern ----
with st.sidebar:
    st.markdown("<div style='padding: 20px 0;'><h2 style='letter-spacing: -1px; margin-bottom: 0;'>SSM Excellence</h2><p style='color: #94a3b8; font-size: 0.85rem;'>The Quantitative Intelligence Agent</p></div>", unsafe_allow_html=True)
    
    st.markdown("### 💠 Workspace")
    my_stocks = load_watchlist()
    name_map = get_stock_names_batch(my_stocks)
    
    for stock in my_stocks:
        with st.container():
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"<span style='font-size: 0.9rem; font-weight: 600;'>{stock}</span> <span style='color: #64748b; font-size: 0.8rem;'>{name_map.get(stock, '')}</span>", unsafe_allow_html=True)
            if c2.button("􀆄", key=f"rm_{stock}", help="Remove"):
                my_stocks.remove(stock)
                save_watchlist(my_stocks)
                st.rerun()

    st.divider()
    with st.expander("➕ Terminal Add"):
        add_code = st.text_input("Symbol", placeholder="Code...", label_visibility="collapsed")
        if st.button("Register Symbol", use_container_width=True):
            if add_code and add_code not in my_stocks:
                my_stocks.append(add_code)
                save_watchlist(my_stocks)
                st.rerun()
    
    st.markdown("<div style='position: fixed; bottom: 20px; font-size: 0.7rem; color: #475569;'>v3.5 Quantum Build</div>", unsafe_allow_html=True)

# ---- Top Header ----
st.markdown("<h2 style='margin-bottom: 0;'>Market Discovery</h2>", unsafe_allow_html=True)

# ---- Main Content ----
tab_main, tab_diag = st.tabs(["📡 Intelligence Stream", "🧬 Stock DNA Analysis"])

with tab_main:
    # 1. Glass Indices Row
    ov = get_market_overview()
    if not ov.empty:
        cols = st.columns(len(ov))
        for i, row in enumerate(ov.itertuples()):
            cols[i].metric(label=row.名称, value=f"{row.最新价:,.1f}", delta=f"{row.涨跌幅:+.2f}%")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. Strategy Grid
    st.markdown("### 📡 Strategy Capture")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("<div style='background: #eff6ff; border-radius: 12px; padding: 15px; border: 1px solid #bfdbfe;'><b style='color: #1e40af;'>💎 Value Discovery</b><p style='margin:0; font-size: 0.8rem; color: #3b82f6;'>Deep value alpha identification.</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown("<div style='background: #f0fdf4; border-radius: 12px; padding: 15px; border: 1px solid #bbf7d0;'><b style='color: #166534;'>🔥 Momentum Burst</b><p style='margin:0; font-size: 0.8rem; color: #22c55e;'>High-volume breakout signals.</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown("<div style='background: #fffbeb; border-radius: 12px; padding: 15px; border: 1px solid #fef3c7;'><b style='color: #92400e;'>🌟 Growth Star</b><p style='margin:0; font-size: 0.8rem; color: #f59e0b;'>Core asset compounding logic.</p></div>", unsafe_allow_html=True)

    strat = st.segmented_control("Capture Engine", ["Value", "Momentum", "Growth"], default="Value", label_visibility="collapsed")
    
    if strat == "Value": df = find_value_stocks()
    elif strat == "Momentum": df = find_momentum_stocks()
    else: df = find_growth_stocks()

    if not df.empty:
        df.insert(0, "Track", False)
        # Advanced Data Grid
        st.markdown("<br>", unsafe_allow_html=True)
        res = st.data_editor(
            df,
            hide_index=True,
            column_config={
                "Track": st.column_config.CheckboxColumn("追踪", width="small"),
                "代码": st.column_config.TextColumn("代码"),
                "涨跌幅": st.column_config.NumberColumn("Change", format="%.2f%%"),
                "最新价": st.column_config.NumberColumn("Price", format="¥%.2f")
            },
            disabled=[c for c in df.columns if c != "Track"],
            use_container_width=True
        )
        
        sel = res[res["Track"] == True]
        if not sel.empty:
            scol1, scol2 = st.columns([1, 4])
            if scol1.button("Register Selected", type="primary", use_container_width=True):
                new = [c for c in sel['代码'] if c not in my_stocks]
                if new:
                    my_stocks.extend(new)
                    save_watchlist(my_stocks)
                    st.toast("Symbols registered to workspace", icon="💠")
                    st.rerun()
            if len(sel) == 1:
                st.session_state['selected_stock'] = sel.iloc[0]['代码']
                st.info(f"Symbol {st.session_state['selected_stock']} locked. Proceed to Stock DNA.")

with tab_diag:
    # 🧬 Decision Logic
    target = st.session_state['selected_stock']
    if target not in my_stocks: my_stocks.insert(0, target)
    
    h1, h2 = st.columns([3, 1])
    sel_stock = h1.selectbox("Target Symbol", my_stocks, index=my_stocks.index(target) if target in my_stocks else 0, format_func=lambda x: f"🧬 {x} {name_map.get(x, '')}", label_visibility="collapsed")
    st.session_state['selected_stock'] = sel_stock
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 🧬 DNA Metrics
    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    kline = fetch_kline("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock)
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Financial Health", f"{f_data.get('score', 0) if f_data else 50}%", "Core Grade")
    m2.metric("RSI Strength", f"{q_metrics.get('rsi', 0):.1f}", "Oscillator")
    m3.metric("Annual Vol", f"{q_metrics.get('volatility_ann', 0):.1f}%", "Risk Profile")
    m4.metric("Agent Verdict", "Overweight" if q_metrics.get('rsi',50) < 45 else "Hold", "AI Logic")

    # 🧬 Visualizer
    c_chart, c_report = st.columns([3, 2])
    
    with c_chart:
        if not kline.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=kline['日期'], open=kline['开盘'], high=kline['最高'], low=kline['最低'], close=kline['收盘'],
                increasing_line_color='#2563eb', decreasing_line_color='#64748b' # Modern Navy/Blue theme
            )])
            fig.update_layout(
                height=500, margin=dict(l=0,r=0,t=0,b=0),
                xaxis_rangeslider_visible=False,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                font=dict(family="JetBrains Mono", size=10)
            )
            st.plotly_chart(fig, use_container_width=True)

    with c_report:
        cached, is_cached = load_cached_report(sel_stock)
        if st.button("🚀 Invoke AI Deep Synthesis", type="primary", use_container_width=True):
            with st.spinner("Synthesizing multi-modal financial data..."):
                rep = generate_ai_report(sel_stock, name_map.get(sel_stock, ''), fetch_research_reports(sel_stock), fetch_trading_signals("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock))
                st.markdown(f"<div class='ai-bubble'>{rep}</div>", unsafe_allow_html=True)
                # Cache
                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f:
                    f.write(rep)
        elif is_cached:
            st.markdown(f"<div class='ai-bubble'>{cached}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='height: 300px; display: flex; align-items: center; justify-content: center; color: #94a3b8; border: 2px dashed #e2e8f0; border-radius: 16px;'>Select Symbol & Invoke Analysis</div>", unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)
st.divider()
st.markdown("<div style='text-align: center; color: #94a3b8; font-size: 0.75rem;'>Quantum SSM v3.5 | Excellence in Quantitative Intelligence</div>", unsafe_allow_html=True)
