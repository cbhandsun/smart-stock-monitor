import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

st.set_page_config(page_title="SSM Quantum Terminal", layout="wide", page_icon="⚛️", initial_sidebar_state="expanded")

# ---- Language Dictionary (v4.0 Alpha) ----
LANG_MAP = {
    "zh": {
        "title": "SSM 智投终端", "subtitle": "Quantum Intelligence v4.0",
        "market_discovery": "📡 实时信号流", "dna_analysis": "🧬 深度决策中心",
        "strat_capture": "策略捕捉引擎", "invoke_ai": "启动多模态 AI 研判",
        "overweight": "建议增持", "hold": "建议观察", "select_invoke": "请锁定标的以启动分析",
        "fin_health": "财务健康分", "rsi_strength": "相对强度(RSI)", "ann_vol": "年化波动率", "agent_verdict": "智能演算结论"
    },
    "en": {
        "title": "SSM Quantum", "subtitle": "Quantum Intelligence v4.0",
        "market_discovery": "📡 Signal Stream", "dna_analysis": "🧬 Decision Center",
        "strat_capture": "Strategy Engine", "invoke_ai": "Invoke Multi-modal AI",
        "overweight": "Overweight", "hold": "Neutral", "select_invoke": "Select Target for Synthesis",
        "fin_health": "Financial Score", "rsi_strength": "RSI (14)", "ann_vol": "Annual Vol", "agent_verdict": "Verdict"
    }
}

if 'lang' not in st.session_state: st.session_state['lang'] = 'zh'
if 'selected_stock' not in st.session_state: st.session_state['selected_stock'] = "601318"
L = LANG_MAP[st.session_state['lang']]

# ---- UI Styling (v4.0 Professional) ----
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono&family=Outfit:wght@400;600;700&display=swap');
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .main { background: #0a0e14; color: #e2e8f0; }
    [data-testid="stSidebar"] { background: #0f172a !important; border-right: 1px solid #1e293b; }
    [data-testid="stMetric"] { background: #161e2e !important; border: 1px solid #1e293b !important; border-radius: 12px !important; padding: 20px !important; }
    .stTabs [data-baseweb="tab-list"] { background: #1e293b; padding: 5px; border-radius: 10px; }
    .stTabs [data-baseweb="tab"] { color: #94a3b8 !important; padding: 8px 20px !important; }
    .stTabs [data-baseweb="tab"][aria-selected="true"] { background: #3b82f6 !important; color: white !important; border-radius: 8px; }
    .ai-box { background: #1e293b; border-left: 4px solid #3b82f6; padding: 20px; border-radius: 0 12px 12px 0; font-size: 0.95rem; line-height: 1.7; }
    </style>
    """, unsafe_allow_html=True)

# ---- Helpers ----
def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        with open(WATCHLIST_FILE, "r") as f: return json.load(f)
    return ["601318"]

def save_watchlist(stocks):
    with open(WATCHLIST_FILE, "w") as f: json.dump(stocks, f)

def load_cached_report(symbol):
    path = f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{symbol}.md"
    if os.path.exists(path):
        with open(path, "r") as f: return f.read(), True
    return None, False

# ---- Sidebar ----
with st.sidebar:
    st.markdown(f"## {L['title']}\n*{L['subtitle']}*")
    l1, l2 = st.columns(2)
    if l1.button("中文", use_container_width=True): st.session_state['lang'] = 'zh'; st.rerun()
    if l2.button("EN", use_container_width=True): st.session_state['lang'] = 'en'; st.rerun()
    
    st.divider()
    my_stocks = load_watchlist()
    name_map = get_stock_names_batch(my_stocks)
    for s in my_stocks:
        c1, c2 = st.columns([4, 1])
        c1.markdown(f"<span style='color:#3b82f6;font-weight:700'>{s}</span> <small>{name_map.get(s, '')}</small>", unsafe_allow_html=True)
        if c2.button("×", key=f"del_{s}"): my_stocks.remove(s); save_watchlist(my_stocks); st.rerun()
    
    with st.expander("Add Symbol"):
        code = st.text_input("Code")
        if st.button("Add"):
            if code and code not in my_stocks: my_stocks.append(code); save_watchlist(my_stocks); st.rerun()

# ---- Main Layout ----
st.header(L['market_discovery'])
tab_stream, tab_diag = st.tabs([L['market_discovery'], L['dna_analysis']])

with tab_stream:
    ov = get_market_overview()
    if not ov.empty:
        cols = st.columns(len(ov))
        for i, r in enumerate(ov.itertuples()):
            cols[i].metric(r.名称, f"{r.最新价:,.1f}", f"{r.涨跌幅:+.2f}%")

    st.markdown(f"### {L['strat_capture']}")
    sc1, sc2, sc3 = st.columns(3)
    with sc1: st.markdown("<div style='background:#1e3a8a;padding:10px;border-radius:8px'>💎 Value Alpha</div>", unsafe_allow_html=True)
    with sc2: st.markdown("<div style='background:#064e3b;padding:10px;border-radius:8px'>🔥 Momentum Max</div>", unsafe_allow_html=True)
    with sc3: st.markdown("<div style='background:#78350f;padding:10px;border-radius:8px'>🌟 Growth Star</div>", unsafe_allow_html=True)
    
    strat = st.segmented_control("Engine", ["Value", "Momentum", "Growth"], default="Value", label_visibility="collapsed")
    df = find_value_stocks() if strat == "Value" else find_momentum_stocks() if strat == "Momentum" else find_growth_stocks()
    
    if not df.empty:
        df.insert(0, "📌", False)
        res = st.data_editor(df, hide_index=True, use_container_width=True)
        sel = res[res["📌"] == True]
        if not sel.empty:
            if st.button("Add to Workspace", type="primary"):
                added = [c for c in sel['代码'] if c not in my_stocks]
                my_stocks.extend(added); save_watchlist(my_stocks); st.toast("Synced!"); st.rerun()
            if len(sel) == 1:
                st.session_state['selected_stock'] = sel.iloc[0]['代码']
                st.info(f"Locked: {st.session_state['selected_stock']}")

with tab_diag:
    target = st.session_state['selected_stock']
    if target not in my_stocks: my_stocks.insert(0, target)
    sel_stock = st.selectbox("Target", my_stocks, index=my_stocks.index(target), format_func=lambda x: f"{x} {name_map.get(x, '')}")
    st.session_state['selected_stock'] = sel_stock
    
    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    kline = fetch_kline("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock)
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(L['fin_health'], f"{f_data.get('score', 0) if f_data else 50}%")
    m2.metric(L['rsi_strength'], f"{q_metrics.get('rsi', 0):.1f}")
    m3.metric(L['ann_vol'], f"{q_metrics.get('volatility_ann', 0):.1f}%")
    m4.metric(L['agent_verdict'], L['overweight'] if q_metrics.get('rsi',50) < 45 else L['hold'])

    col_c, col_a = st.columns([2, 1])
    with col_c:
        if not kline.empty:
            # Professional Dual Chart: Price + Volume
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
            # Candlestick
            fig.add_trace(go.Candlestick(x=kline['日期'], open=kline['开盘'], high=kline['最高'], low=kline['最低'], close=kline['收盘'], name="Price"), row=1, col=1)
            # Volume
            colors = ['#ef5350' if c < o else '#26a69a' for c, o in zip(kline['收盘'], kline['开盘'])]
            fig.add_trace(go.Bar(x=kline['日期'], y=kline.get('成交额', []), name="Volume", marker_color=colors), row=2, col=1)
            fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

    with col_a:
        cached, is_cached = load_cached_report(sel_stock)
        if st.button(L['invoke_ai'], type="primary", use_container_width=True):
            with st.spinner("Quantum Reasoning in Progress..."):
                rep = generate_ai_report(sel_stock, name_map.get(sel_stock, ''), fetch_research_reports(sel_stock), fetch_trading_signals("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock))
                st.markdown(f"<div class='ai-box'>{rep}</div>", unsafe_allow_html=True)
                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f: f.write(rep)
        elif is_cached: st.markdown(f"<div class='ai-box'>{cached}</div>", unsafe_allow_html=True)
        else: st.info(L['select_invoke'])

st.divider()
st.caption("Quantum SSM v4.0 | Financial Intelligence Terminal")
