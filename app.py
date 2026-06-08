import streamlit as st
import logging
import importlib
import os
from main import get_stock_names_batch
from pages import load_watchlist, save_watchlist
from database.models import init_db

# Initialize postgres early
init_db(os.environ.get("DATABASE_URL", "sqlite:///./data/stock_monitor.db"))

# ---- 页面配置 (Page Configuration) ----
st.set_page_config(
    page_title="SSM 机构级量化工作站 v8.0",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---- 样式加载 (Custom CSS) - 自愈鲁棒版 ----
try:
    with open('static/style.css', 'r') as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except Exception:
    logging.warning("⚠️ 样式加载失败，系统将采用极简 UI")

# ---- 数据状态自愈层 (Persistence Layer) ----
if 'page' in st.query_params:
    st.session_state['current_page'] = st.query_params['page']
elif 'current_page' not in st.session_state:
    st.session_state['current_page'] = 'market'

if 'symbol' in st.query_params:
    st.session_state['selected_stock'] = st.query_params['symbol']
elif 'selected_stock' not in st.session_state:
    st.session_state['selected_stock'] = '601933'

# ---- 数据初始化 (Data Pre-loading) ----
my_stocks = load_watchlist()
name_map = get_stock_names_batch(my_stocks + ['300750', '600519', '000001', '601933'])

# ---- 本地化系统 (Localization) ----
L = {
    'market_discovery': '实时信号流',
    'stock_dna': '研判 DNA',
    'alpha_radar': '宏观雷达',
    'ai_analyst': 'AI 策略师',
    'anomaly_detect': '异动监控'
}
NEW_MODULES_AVAILABLE = True

# ---- 页面动态加载内核 (Lazy Route Core) ----
def _get_page(page_name):
    try:
        # 兼容性重定向
        if page_name == 'macro': return importlib.import_module('pages.macro')
        return importlib.import_module(f'pages.{page_name}')
    except Exception as e:
        logging.error(f"Failed to load page {page_name}: {e}")
        return None

def _route(page_name, render_args):
    """主路由执行引擎"""
    mod = _get_page(page_name)
    if mod:
        mod.render(*render_args)
    else:
        st.warning(f"⚠️ 模块 `{page_name}` 未加载，请检查部署日志")

# ---- 全量路由配置项 (PAGE_RENDER_ARGS) - 逻辑定义置顶 ----
PAGE_RENDER_ARGS = {
    'macro':              (L,),
    'market':             (L, my_stocks, name_map),
    'recommend':          (L, my_stocks, name_map),
    'ai_tracker':         (L, my_stocks, name_map),
    'settings':           (L, NEW_MODULES_AVAILABLE),
    'data_manager':       (L,),
    'data_health':        (L,),                          # ← 数据完整性监控
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

# ---- 认证拦截层 (Security Gatekeeper) ----
try:
    from pages._login import check_auth, render_login_page, render_user_menu
except ImportError:
    check_auth = lambda: True
    render_login_page = lambda: True
    render_user_menu = lambda: None

# 强验证卡口：如果未登录，阻截所有渲染并仅展示登录页
if not check_auth():
    render_login_page()
    st.stop()

# ---- 侧边栏导航矩阵 (Hardened Navigation Matrix) ----
try:
    from components.sidebar import render_sidebar
    render_sidebar(L, name_map, NEW_MODULES_AVAILABLE)
except Exception as e:
    logging.error(f"Failed to load sidebar: {e}")
    st.sidebar.error("侧边栏加载失败")

# ---- 主界面渲染执行 ----
st.query_params['page'] = st.session_state.get('current_page', 'market')
st.query_params['symbol'] = st.session_state.get('selected_stock', '601933')

current_page = st.session_state.get('current_page', 'market')
render_args = PAGE_RENDER_ARGS.get(current_page, (L,))

_route(current_page, render_args)
