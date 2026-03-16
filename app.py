import streamlit as st
import logging
import importlib
from main import get_stock_names_batch
from pages import load_watchlist, save_watchlist
from utils.i18n import get_lang
from pages._login import check_auth, render_login_page, render_user_menu, AUTH_AVAILABLE

logger = logging.getLogger(__name__)

# ---- 懒加载页面模块 (节省 ~3.7s 启动时间) ----
_page_cache = {}
def _get_page(name):
    """Lazy import page module"""
    if name not in _page_cache:
        try:
            _page_cache[name] = importlib.import_module(f'pages.{name}')
        except ImportError as e:
            logger.warning(f"页面模块 {name} 不可用: {e}")
            return None
    return _page_cache[name]

NEW_MODULES_AVAILABLE = True  # 延迟到实际路由时才知道

# ---- Page Config ----
st.set_page_config(
    page_title="SSM Quantum Pro v7.0",
    layout="wide",
    page_icon="⚛️",
    initial_sidebar_state="expanded"
)

# ---- Session State Initialization ----
if 'lang' not in st.session_state:
    st.session_state['lang'] = 'zh'
if 'selected_stock' not in st.session_state:
    st.session_state['selected_stock'] = "601318"
if 'theme' not in st.session_state:
    st.session_state['theme'] = 'dark'
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 'market'
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = 'default_user'
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

# ---- Language Dictionary (centralized) ----
L = get_lang(st.session_state['lang'])

# ---- Auth Gate ----
# if AUTH_AVAILABLE and not check_auth():
#     render_login_page()
#     st.stop()

# ---- Theme CSS ----
theme_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800&family=JetBrains+Mono&display=swap');

    /* Global Typography */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    h1, h2, h3, h4, h5, h6, .st-emotion-cache-10trblm, [data-testid="stMetricLabel"] > div, .strat-banner {
        font-family: 'Outfit', sans-serif !important;
        letter-spacing: -0.02em;
    }

    /* Core Background Colors */
    .main {
        background-color: #0b1120;
        color: #f8fafc;
    }

    /* Glassmorphism Metrics */
    div[data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.4) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        box-shadow: 0 4px 24px -4px rgba(0, 0, 0, 0.2) !important;
        border-radius: 16px !important;
        padding: 24px !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
    }
    
    div[data-testid="stMetric"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 32px -4px rgba(56, 189, 248, 0.15) !important;
        border-color: rgba(56, 189, 248, 0.3) !important;
    }

    div[data-testid="stMetricLabel"] > div {
        color: #94a3b8 !important;
        font-weight: 500 !important;
        font-size: 0.95rem !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    div[data-testid="stMetricValue"] > div {
        color: #f8fafc !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        font-size: 2.5rem !important;
    }
    div[data-testid="stMetricDelta"] svg {
        margin-top: 2px;
    }

    /* Premium Sidebar */
    [data-testid="stSidebar"] {
        background-color: #030712 !important;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }

    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p, [data-testid="stSidebar"] label, [data-testid="stSidebar"] span {
        color: #f1f5f9 !important;
    }

    /* Standard Buttons */
    button[data-testid="baseButton-secondary"] {
        background-color: rgba(30, 41, 59, 0.6) !important;
        color: #cbd5e1 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: 10px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    button[data-testid="baseButton-secondary"]:hover {
        background-color: #1e293b !important;
        border-color: #38bdf8 !important;
        color: #fff !important;
        box-shadow: 0 0 15px rgba(56, 189, 248, 0.2);
    }

    /* Primary Buttons (Active State) */
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #38bdf8 100%) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border: none !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 14px rgba(56, 189, 248, 0.3) !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    button[data-testid="baseButton-primary"]:hover {
        box-shadow: 0 6px 20px rgba(56, 189, 248, 0.5) !important;
        transform: translateY(-1px);
    }

    /* Segmented Controls (Tabs) */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(30, 41, 59, 0.5);
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 6px;
        border-radius: 14px;
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        color: #94a3b8 !important;
        font-weight: 500;
        border-radius: 10px;
        padding: 8px 16px;
        transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: #e2e8f0 !important;
        background: rgba(255,255,255,0.05);
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background: #1e293b !important;
        color: white !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
        border: 1px solid rgba(255,255,255,0.1);
    }

    /* AI Box Premium Styling */
    .ai-box {
        background: linear-gradient(145deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(139, 92, 246, 0.3);
        border-left: 4px solid #8b5cf6;
        padding: 28px;
        border-radius: 16px;
        color: #f1f5f9;
        line-height: 1.8;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
    .ai-box h3 {
        color: #a78bfa !important;
        margin-top: 0;
        font-family: 'Outfit', sans-serif;
    }

    /* Hide Streamlit native sidebar navigation */
    [data-testid="stSidebarNav"] {
        display: none !important;
    }

    /* ---- 导航分组 Expander 美化 ---- */
    [data-testid="stSidebar"] details {
        background: rgba(15, 23, 42, 0.5) !important;
        border: 1px solid rgba(255, 255, 255, 0.06) !important;
        border-radius: 12px !important;
        margin-bottom: 6px !important;
        transition: border-color 0.2s ease;
    }
    [data-testid="stSidebar"] details:hover {
        border-color: rgba(56, 189, 248, 0.2) !important;
    }
    [data-testid="stSidebar"] details summary {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
        color: #94a3b8 !important;
    }
    [data-testid="stSidebar"] details[open] summary {
        color: #38bdf8 !important;
    }

    /* ---- 骨架屏加载动画 ---- */
    @keyframes skeleton-pulse {
        0% { opacity: 0.6; }
        50% { opacity: 1; }
        100% { opacity: 0.6; }
    }
    .skeleton-loading {
        animation: skeleton-pulse 1.5s ease-in-out infinite;
        background: linear-gradient(90deg, rgba(30,41,59,0.5) 25%, rgba(51,65,85,0.5) 50%, rgba(30,41,59,0.5) 75%);
        background-size: 200% 100%;
        border-radius: 8px;
        height: 20px;
        margin: 8px 0;
    }

    /* ---- 导航按钮活跃态发光 ---- */
    [data-testid="stSidebar"] button[data-testid="baseButton-primary"] {
        box-shadow: 0 0 12px rgba(56, 189, 248, 0.4), 0 4px 14px rgba(56, 189, 248, 0.2) !important;
    }

    </style>
"""
st.markdown(theme_css, unsafe_allow_html=True)

# ---- Sidebar Navigation ----
with st.sidebar:
    st.markdown(f"## {L['title']}\n<span style='color:#94a3b8'>Quantum Pro v7.0</span>", unsafe_allow_html=True)

    # User menu (if authenticated)
    if AUTH_AVAILABLE and check_auth():
        render_user_menu()

    # Language Switch
    l1, l2 = st.columns(2)
    if l1.button("中文", use_container_width=True):
        st.session_state['lang'] = 'zh'
        st.rerun()
    if l2.button("EN", use_container_width=True):
        st.session_state['lang'] = 'en'
        st.rerun()

    st.divider()

    # ---- ⭐ 我的自选 (可折叠, 含涨跌标签) ----
    my_stocks = load_watchlist()
    name_map = get_stock_names_batch(my_stocks)

    # 尝试批量获取实时行情 (轻量级) — Redis L1 缓存 30s
    _quotes = {}
    if my_stocks:
        try:
            from core.cache import RedisCache
            _rc = RedisCache()
            if _rc.ping():
                cached = _rc.get("sidebar:watchlist_quotes")
                if cached:
                    _quotes = cached
        except Exception:
            pass

        if not _quotes:
            try:
                import requests
                sina_codes = [f"{'s_sh' if c.startswith('6') else 's_sz'}{c}" for c in my_stocks[:10]]
                url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
                headers = {'Referer': 'https://finance.sina.com.cn/'}
                r = requests.get(url, headers=headers, timeout=3)
                for line in r.text.strip().split(';'):
                    if '="' in line:
                        val = line.split('="')[1].strip('"')
                        parts = val.split(',')
                        if len(parts) > 3:
                            code = parts[0]
                            _quotes[code] = {'price': float(parts[1]), 'change': float(parts[3])}
                # 写入 Redis
                try:
                    _rc.set("sidebar:watchlist_quotes", _quotes, expire=30)
                except Exception:
                    pass
            except Exception:
                pass

    with st.expander(f"⭐ 我的自选 ({len(my_stocks)})", expanded=False):
        for s in my_stocks[:10]:
            # 查找行情
            q = None
            s_name = name_map.get(s, '')
            for qname, qdata in _quotes.items():
                if s_name and s_name in qname:
                    q = qdata
                    break

            c1, c2 = st.columns([5, 1])
            with c1:
                # 构建标签
                if q:
                    chg = q['change']
                    color = "#ef4444" if chg >= 0 else "#10b981"
                    arrow = "▲" if chg >= 0 else "▼"
                    badge = f"<span style='color:{color}; font-size:0.7rem; font-weight:500;'>{arrow}{abs(chg):.1f}%</span>"
                else:
                    badge = ""

                st.markdown(
                    f"<div style='padding:2px 0; font-size:0.85rem;'>"
                    f"<span style='color:#cbd5e1;'>{s}</span> "
                    f"<span style='color:#94a3b8; font-size:0.75rem;'>{s_name}</span> "
                    f"{badge}</div>",
                    unsafe_allow_html=True
                )
                if st.button(f"查看", key=f"qwl_{s}", use_container_width=True, type="secondary"):
                    st.session_state['selected_stock'] = s
                    st.rerun()
            with c2:
                if st.button("×", key=f"del_{s}"):
                    if s in my_stocks:
                        my_stocks.remove(s)
                        save_watchlist(my_stocks)
                        st.rerun()

    st.divider()

    # ---- 🧭 功能导航 (分组 Expander) ----
    def _nav_btn(key, label):
        """渲染单个导航按钮，高亮当前页"""
        btn_type = "primary" if st.session_state['current_page'] == key else "secondary"
        if st.button(label, use_container_width=True, type=btn_type, key=f"nav_{key}"):
            st.session_state['current_page'] = key
            st.rerun()

    with st.expander("📡 看盘中心", expanded=True):
        _nav_btn('market', L['market_discovery'])
        _nav_btn('ai_tracker', '📡 AI 赛道雷达')
        _nav_btn('portfolio', L['portfolio'])

    with st.expander("🤖 AI 智能体", expanded=False):
        _nav_btn('ai_chat', L['ai_chat'])
        _nav_btn('investment_advisor', L['investment_advisor'])
        _nav_btn('predict', L['predict'])
        _nav_btn('sentiment', L['sentiment'])

    with st.expander("🔬 量化研究", expanded=False):
        _nav_btn('backtest', L['backtest'])
        _nav_btn('research', L['research'])
        _nav_btn('research_analyzer', L['research_analyzer'])
        _nav_btn('anomaly', L['anomaly'])

    with st.expander("⚙️ 系统工具", expanded=False):
        _nav_btn('alerts', L['alerts'])
        _nav_btn('settings', L['settings'])

    st.divider()

# ---- 全局标的指示器 ----
from components.ui_components import stock_context_bar
stock_context_bar(name_map)

# ---- 页面路由 (延迟加载) ----
current_page = st.session_state['current_page']

def _route(page_name, render_args):
    """Lazy route: import module only when needed"""
    mod = _get_page(page_name)
    if mod:
        mod.render(*render_args)
    else:
        st.warning(f"⚠️ 模块 `{page_name}` 未加载，请检查依赖安装")

PAGE_RENDER_ARGS = {
    'market':             (L, my_stocks, name_map),
    'ai_tracker':         (L, my_stocks, name_map),
    'settings':           (L, NEW_MODULES_AVAILABLE),
    'research_analyzer':  (L, name_map),
    'portfolio':          (L,),
    'alerts':             (L,),
    'backtest':           (L,),
    'research':           (L, my_stocks, name_map),
    'ai_chat':            (L,),
    'predict':            (L,),
    'sentiment':          (L, my_stocks, name_map),
    'anomaly':            (L, my_stocks, name_map),
    'investment_advisor': (L,),
}

if current_page in PAGE_RENDER_ARGS:
    _route(current_page, PAGE_RENDER_ARGS[current_page])
else:
    st.error(f"未知页面: {current_page}")

st.divider()
st.caption("SSM Quantum Pro v7.0 | AI 量化投研工作站")
