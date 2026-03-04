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

# ---- Language Dictionary ----
LANG_MAP = {
    "zh": {
        "title": "SSM 智投终端",
        "subtitle": "量化智能分析引擎",
        "workspace": "💠 工作区",
        "watchlist": "⭐ 自选股监控",
        "add_symbol": "➕ 添加标的",
        "symbol_placeholder": "代码...",
        "register_btn": "注册代码",
        "market_discovery": "行情发现",
        "intel_stream": "📡 智能捕获流",
        "dna_analysis": "🧬 股票 DNA 研判",
        "strategy_capture": "📡 策略捕获",
        "strat_value": "💎 价值挖掘",
        "strat_momentum": "🔥 强力动能",
        "strat_growth": "🌟 稳健成长",
        "strat_value_desc": "深度价值 Alpha 识别",
        "strat_momentum_desc": "放量突破信号捕获",
        "strat_growth_desc": "核心资产复利逻辑",
        "engine_label": "捕获引擎",
        "track": "追踪",
        "code": "代码",
        "change": "涨跌幅",
        "price": "价格",
        "register_selected": "注册选中标的",
        "lock_msg": "标的 {} 已锁定，请前往 DNA 研判中心",
        "target_symbol": "研判对象",
        "fin_health": "财务健康度",
        "rsi_strength": "RSI 强度",
        "ann_vol": "年化波动率",
        "agent_verdict": "AI 实时判定",
        "grade": "核心评级",
        "oscillator": "震荡指标",
        "risk_profile": "风险特征",
        "ai_logic": "智能逻辑",
        "overweight": "建议增持",
        "hold": "建议观察",
        "invoke_ai": "🚀 启动 AI 深度合成研判",
        "synthesizing": "正在合成多模态金融数据...",
        "select_invoke": "请选择标的并启动分析",
        "sys_status": "🌐 系统状态",
        "engine_running": "核心引擎: 运行中",
        "data_source": "数据源",
        "proxy_mode": "代理中转",
        "direct_mode": "直连模式"
    },
    "en": {
        "title": "SSM Excellence",
        "subtitle": "Quantitative Intelligence Engine",
        "workspace": "💠 Workspace",
        "watchlist": "⭐ Watchlist",
        "add_symbol": "➕ Terminal Add",
        "symbol_placeholder": "Code...",
        "register_btn": "Register Symbol",
        "market_discovery": "Market Discovery",
        "intel_stream": "📡 Intelligence Stream",
        "dna_analysis": "🧬 Stock DNA Analysis",
        "strategy_capture": "📡 Strategy Capture",
        "strat_value": "💎 Value Discovery",
        "strat_momentum": "🔥 Momentum Burst",
        "strat_growth": "🌟 Growth Star",
        "strat_value_desc": "Deep value alpha identification.",
        "strat_momentum_desc": "High-volume breakout signals.",
        "strat_growth_desc": "Core asset compounding logic.",
        "engine_label": "Capture Engine",
        "track": "Track",
        "code": "Symbol",
        "change": "Change",
        "price": "Price",
        "register_selected": "Register Selected",
        "lock_msg": "Symbol {} locked. Proceed to Stock DNA.",
        "target_symbol": "Target Symbol",
        "fin_health": "Financial Health",
        "rsi_strength": "RSI Strength",
        "ann_vol": "Annual Vol",
        "agent_verdict": "Agent Verdict",
        "grade": "Core Grade",
        "oscillator": "Oscillator",
        "risk_profile": "Risk Profile",
        "ai_logic": "AI Logic",
        "overweight": "Overweight",
        "hold": "Hold",
        "invoke_ai": "🚀 Invoke AI Deep Synthesis",
        "synthesizing": "Synthesizing multi-modal financial data...",
        "select_invoke": "Select Symbol & Invoke Analysis",
        "sys_status": "🌐 System Status",
        "engine_running": "Core Engine: Online",
        "data_source": "Data Source",
        "proxy_mode": "Proxy Tunnel",
        "direct_mode": "Direct Mode"
    }
}

# ---- Session State ----
if 'lang' not in st.session_state:
    st.session_state['lang'] = 'zh'
if 'selected_stock' not in st.session_state:
    st.session_state['selected_stock'] = "601318"

L = LANG_MAP[st.session_state['lang']]

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

    div[data-testid="stMetric"] {
        background: var(--card-bg) !important;
        backdrop-filter: blur(10px);
        border: 1px solid var(--glass-border) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.05) !important;
    }

    [data-testid="stSidebar"] {
        background: #0f172a !important;
        border-right: 1px solid #1e293b;
    }
    
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] p {
        color: #f8fafc !important;
    }

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

    .ai-bubble {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 24px;
        line-height: 1.8;
        font-size: 1rem;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.04);
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

# ---- Sidebar Modern ----
with st.sidebar:
    st.markdown(f"<div style='padding: 20px 0;'><h2 style='letter-spacing: -1px; margin-bottom: 0;'>{L['title']}</h2><p style='color: #94a3b8; font-size: 0.85rem;'>{L['subtitle']}</p></div>", unsafe_allow_html=True)
    
    # Language Switch
    l_c1, l_c2 = st.columns(2)
    if l_c1.button("中文", use_container_width=True, type="primary" if st.session_state['lang'] == 'zh' else "secondary"):
        st.session_state['lang'] = 'zh'
        st.rerun()
    if l_c2.button("English", use_container_width=True, type="primary" if st.session_state['lang'] == 'en' else "secondary"):
        st.session_state['lang'] = 'en'
        st.rerun()

    st.markdown(f"### {L['workspace']}")
    my_stocks = load_watchlist()
    name_map = get_stock_names_batch(my_stocks)
    
    for stock in my_stocks:
        with st.container():
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"<span style='font-size: 0.9rem; font-weight: 600;'>{stock}</span> <span style='color: #64748b; font-size: 0.8rem;'>{name_map.get(stock, '')}</span>", unsafe_allow_html=True)
            if c2.button("×", key=f"rm_{stock}"):
                my_stocks.remove(stock)
                save_watchlist(my_stocks)
                st.rerun()

    st.divider()
    with st.expander(L['add_symbol']):
        add_code = st.text_input(L['code'], placeholder=L['symbol_placeholder'], label_visibility="collapsed")
        if st.button(L['register_btn'], use_container_width=True):
            if add_code and add_code not in my_stocks:
                my_stocks.append(add_code)
                save_watchlist(my_stocks)
                st.rerun()
    
    st.markdown(f"### {L['sys_status']}")
    st.success(L['engine_running'])
    st.info(f"{L['data_source']}: {L['proxy_mode'] if 'HTTP_PROXY' in os.environ else L['direct_mode']}")

# ---- Top Header ----
st.markdown(f"<h2 style='margin-bottom: 0;'>{L['market_discovery']}</h2>", unsafe_allow_html=True)

# ---- Main Content ----
tab_main, tab_diag = st.tabs([L['intel_stream'], L['dna_analysis']])

with tab_main:
    # 1. Glass Indices Row
    ov = get_market_overview()
    if not ov.empty:
        cols = st.columns(len(ov))
        for i, row in enumerate(ov.itertuples()):
            cols[i].metric(label=row.名称, value=f"{row.最新价:,.1f}", delta=f"{row.涨跌幅:+.2f}%")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 2. Strategy Grid
    st.markdown(f"### {L['strategy_capture']}")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"<div style='background: #eff6ff; border-radius: 12px; padding: 15px; border: 1px solid #bfdbfe;'><b style='color: #1e40af;'>{L['strat_value']}</b><p style='margin:0; font-size: 0.8rem; color: #3b82f6;'>{L['strat_value_desc']}</p></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div style='background: #f0fdf4; border-radius: 12px; padding: 15px; border: 1px solid #bbf7d0;'><b style='color: #166534;'>{L['strat_momentum']}</b><p style='margin:0; font-size: 0.8rem; color: #22c55e;'>{L['strat_momentum_desc']}</p></div>", unsafe_allow_html=True)
    with c3:
        st.markdown(f"<div style='background: #fffbeb; border-radius: 12px; padding: 15px; border: 1px solid #fef3c7;'><b style='color: #92400e;'>{L['strat_growth']}</b><p style='margin:0; font-size: 0.8rem; color: #f59e0b;'>{L['strat_growth_desc']}</p></div>", unsafe_allow_html=True)

    strat_key = st.segmented_control(L['engine_label'], ["Value", "Momentum", "Growth"], default="Value", label_visibility="collapsed")
    
    if strat_key == "Value": df = find_value_stocks()
    elif strat_key == "Momentum": df = find_momentum_stocks()
    else: df = find_growth_stocks()

    if not df.empty:
        df.insert(0, L['track'], False)
        st.markdown("<br>", unsafe_allow_html=True)
        res = st.data_editor(
            df,
            hide_index=True,
            column_config={
                L['track']: st.column_config.CheckboxColumn(L['track'], width="small"),
                "代码": st.column_config.TextColumn(L['code']),
                "涨跌幅": st.column_config.NumberColumn(L['change'], format="%.2f%%"),
                "最新价": st.column_config.NumberColumn(L['price'], format="¥%.2f")
            },
            disabled=[c for c in df.columns if c != L['track']],
            use_container_width=True
        )
        
        sel = res[res[L['track']] == True]
        if not sel.empty:
            scol1, scol2 = st.columns([1, 4])
            if scol1.button(L['register_selected'], type="primary", use_container_width=True):
                new = [c for c in sel['代码'] if c not in my_stocks]
                if new:
                    my_stocks.extend(new)
                    save_watchlist(my_stocks)
                    st.toast("Symbols registered", icon="💠")
                    st.rerun()
            if len(sel) == 1:
                st.session_state['selected_stock'] = sel.iloc[0]['代码']
                st.info(L['lock_msg'].format(st.session_state['selected_stock']))

with tab_diag:
    # 🧬 Decision Logic
    target = st.session_state['selected_stock']
    if target not in my_stocks: my_stocks.insert(0, target)
    
    h1, h2 = st.columns([3, 1])
    sel_stock = h1.selectbox(L['target_symbol'], my_stocks, index=my_stocks.index(target) if target in my_stocks else 0, format_func=lambda x: f"🧬 {x} {name_map.get(x, '')}", label_visibility="collapsed")
    st.session_state['selected_stock'] = sel_stock
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 🧬 DNA Metrics
    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    kline = fetch_kline("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock)
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(L['fin_health'], f"{f_data.get('score', 0) if f_data else 50}%", L['grade'])
    m2.metric(L['rsi_strength'], f"{q_metrics.get('rsi', 0):.1f}", L['oscillator'])
    m3.metric(L['ann_vol'], f"{q_metrics.get('volatility_ann', 0):.1f}%", L['risk_profile'])
    m4.metric(L['agent_verdict'], L['overweight'] if q_metrics.get('rsi',50) < 45 else L['hold'], L['ai_logic'])

    # 🧬 Visualizer
    c_chart, c_report = st.columns([3, 2])
    
    with c_chart:
        if not kline.empty:
            fig = go.Figure(data=[go.Candlestick(
                x=kline['日期'], open=kline['开盘'], high=kline['最高'], low=kline['最低'], close=kline['收盘'],
                increasing_line_color='#2563eb', decreasing_line_color='#64748b'
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
        if st.button(L['invoke_ai'], type="primary", use_container_width=True):
            with st.spinner(L['synthesizing']):
                rep = generate_ai_report(sel_stock, name_map.get(sel_stock, ''), fetch_research_reports(sel_stock), fetch_trading_signals("sh"+sel_stock if sel_stock.startswith('6') else "sz"+sel_stock))
                st.markdown(f"<div class='ai-bubble'>{rep}</div>", unsafe_allow_html=True)
                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f:
                    f.write(rep)
        elif is_cached:
            st.markdown(f"<div class='ai-bubble'>{cached}</div>", unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='height: 300px; display: flex; align-items: center; justify-content: center; color: #94a3b8; border: 2px dashed #e2e8f0; border-radius: 16px;'>{L['select_invoke']}</div>", unsafe_allow_html=True)

st.markdown("<br><br>", unsafe_allow_html=True)
st.divider()
st.markdown(f"<div style='text-align: center; color: #94a3b8; font-size: 0.75rem;'>Quantum SSM v3.5 | 2026 Excellence in Quantitative Intelligence</div>", unsafe_allow_html=True)
