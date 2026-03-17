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

# ---- PostgreSQL 初始化 (仅执行一次) ----
if 'pg_initialized' not in st.session_state:
    try:
        from core.database import init_tables
        init_tables()
    except Exception as e:
        logger.warning(f"PG 初始化跳过: {e}")
    st.session_state['pg_initialized'] = True

# ---- Auth Gate ----
# if AUTH_AVAILABLE and not check_auth():
#     render_login_page()
#     st.stop()

# ---- Theme CSS (external file) ----
import pathlib as _pathlib
_css_path = _pathlib.Path(__file__).parent / 'static' / 'theme.css'
if _css_path.exists():
    st.markdown(f'<style>{_css_path.read_text()}</style>', unsafe_allow_html=True)
else:
    logger.warning("static/theme.css not found, using defaults")

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

    # 侧边栏行情 — @st.cache_data 避免每次 rerun 阻塞
    @st.cache_data(ttl=30, show_spinner=False)
    def _fetch_sidebar_quotes(stocks_tuple):
        """缓存侧边栏行情 (30s TTL)"""
        quotes = {}
        if not stocks_tuple:
            return quotes
        try:
            import requests
            sina_codes = [f"{'s_sh' if c.startswith('6') else 's_sz'}{c}" for c in stocks_tuple[:10]]
            url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
            headers = {'Referer': 'https://finance.sina.com.cn/'}
            r = requests.get(url, headers=headers, timeout=3)
            for line in r.text.strip().split(';'):
                if '="' in line:
                    val = line.split('="')[1].strip('"')
                    parts = val.split(',')
                    if len(parts) > 3:
                        code = parts[0]
                        quotes[code] = {'price': float(parts[1]), 'change': float(parts[3])}
        except Exception:
            pass
        return quotes

    _quotes = _fetch_sidebar_quotes(tuple(my_stocks))

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

    # ---- 系统状态指示器 ----
    import datetime as _dt
    _redis_ok = False
    try:
        from core.cache import RedisCache as _RC
        _rc_inst = _RC()
        _redis_ok = _rc_inst.ping()
    except Exception:
        pass
    _ts_ok = False
    try:
        from core.tushare_client import get_ts_client as _get_ts
        _ts_ok = _get_ts().available
    except Exception:
        pass

    _r_dot = '🟢' if _redis_ok else '🔴'
    _t_dot = '🟢' if _ts_ok else '🔴'
    _now = _dt.datetime.now().strftime('%H:%M')
    st.markdown(f'''
<div style="background: rgba(15,23,42,0.5); border: 1px solid rgba(255,255,255,0.04);
     border-radius: 10px; padding: 10px 12px; font-size: 0.72rem; line-height: 1.8;">
    <div style="color: #475569; font-weight: 600; margin-bottom: 2px;">系统状态</div>
    <div style="color: #94a3b8;">{_r_dot} Redis {'在线' if _redis_ok else '离线'}
        &nbsp; {_t_dot} Tushare {'在线' if _ts_ok else '离线'}</div>
    <div style="color: #475569;">🕐 {_now} 更新</div>
</div>
''', unsafe_allow_html=True)

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

st.markdown('''<div style="margin-top: 32px; padding-top: 16px;
    border-top: 1px solid rgba(255,255,255,0.04);">
    <div style="text-align: center; font-size: 0.75rem; color: #475569;">
        <span style="font-family: Outfit, sans-serif; font-weight: 600; letter-spacing: 0.05em;">SSM QUANTUM PRO</span>
        <span style="margin-left: 6px; background: rgba(56,189,248,0.1); color: #38bdf8;
              padding: 1px 8px; border-radius: 8px; font-size: 0.68rem;">v7.0</span>
        <br>
        <span style="color: #334155;">AI 量化投研工作站</span>
    </div>
</div>''', unsafe_allow_html=True)
