import streamlit as st
import logging
import importlib
import datetime as _dt
from main import get_stock_names_batch
from pages import load_watchlist, save_watchlist

# ---- 页面配置 (Page Configuration) ----
st.set_page_config(
    page_title="SSM 机构级量化工作站 v7.0",
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
if 'current_page' not in st.session_state:
    st.session_state['current_page'] = 'market'
if 'selected_stock' not in st.session_state:
    st.session_state['selected_stock'] = '601318'

# ---- 数据初始化 (Data Pre-loading) ----
my_stocks = load_watchlist()
name_map = get_stock_names_batch(my_stocks + ['300750', '600519', '000001', '601318'])

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
    'ai_tracker':         (L, my_stocks, name_map),
    'settings':           (L, NEW_MODULES_AVAILABLE),
    'data_manager':       (L,),
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

# ---- 侧边栏导航矩阵 (Hardened Navigation Matrix) ----
with st.sidebar:
    st.markdown("""<div style='text-align: center; padding: 10px 0;'>
        <div style='font-size: 1.8rem; font-weight: 800; color: #38bdf8;'>SSM QUANT</div>
        <div style='font-size: 0.7rem; color: #64748b; letter-spacing: 2px;'>INSTITUTIONAL v7.0</div>
    </div>""", unsafe_allow_html=True)
    
    # 核心监控区
    if st.button("📈 实时看盘信号", key="PRO_SSM_V7_sidebar_market", use_container_width=True, type="primary" if st.session_state['current_page']=='market' else "secondary"):
        st.session_state['current_page'] = 'market'
        st.rerun()

    if st.button("🧪 深度研究 DNA", key="PRO_SSM_V7_sidebar_research", use_container_width=True, type="primary" if st.session_state['current_page']=='research' else "secondary"):
        st.session_state['current_page'] = 'research'
        st.rerun()
        
    if st.button("💼 资产组合管理", key="PRO_SSM_V7_sidebar_portfolio", use_container_width=True, type="primary" if st.session_state['current_page']=='portfolio' else "secondary"):
        st.session_state['current_page'] = 'portfolio'
        st.rerun()

    st.divider()

    # AI 智能集群 (AI Blocks)
    with st.expander("🤖 AI 策略矩阵 (Alpha Tracker)"):
        ai_navs = [
            ("📡 信号追踪器", 'ai_tracker'),
            ("💬 AI 策略师", 'ai_chat'),
            ("💡 投顾建议", 'investment_advisor'),
            ("🎭 市场情绪说", 'sentiment')
        ]
        for label, target in ai_navs:
            if st.button(label, key=f"PRO_SSM_V7_sidebar_{target}", use_container_width=True):
                st.session_state['current_page'] = target
                st.rerun()

    # 高级分析矩阵 (Analytic Blocks)
    with st.expander("🧪 量化分析矩阵 (Lab)"):
        lab_navs = [
            ("📊 宏观雷达", 'macro'),
            ("🔍 异动监测", 'anomaly'),
            ("📈 预测中心", 'predict'),
            ("🛠️ 技术回测", 'backtest'),
            ("🔬 研究员分析", 'research_analyzer')
        ]
        for label, target in lab_navs:
            if st.button(label, key=f"PRO_SSM_V7_sidebar_{target}", use_container_width=True):
                st.session_state['current_page'] = target
                st.rerun()

    # 系统运维
    with st.expander("⚙️ 系统与运维 (Ops)"):
        ops_navs = [
            ("🔌 数据管理", 'data_manager'),
            ("🔔 预警中心", 'alerts'),
            ("🛠️ 设置中心", 'settings')
        ]
        for label, target in ops_navs:
            if st.button(label, key=f"PRO_SSM_V7_sidebar_{target}", use_container_width=True):
                st.session_state['current_page'] = target
                st.rerun()

    st.divider()
    # 全局标的扫描器 (加固引用)
    try:
        from components.ui_components import stock_context_bar, stock_selector
        stock_context_bar(name_map)
        stock_selector(label="快捷代码分析", key_suffix="PRO_SSM_V7_sidebar_entry")
    except Exception:
        pass

    # 页脚状态
    st.markdown('''<div style="margin-top: 32px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.04);">
        <div style="text-align: center; font-size: 0.72rem; color: #475569;">
            SSM QUANTUM PRO <span style="background: rgba(56,189,248,0.1); color: #38bdf8; padding: 1px 6px; border-radius: 4px;">v7.0</span>
            <br>AI 量化投研工作站 (2026)
        </div>
    </div>''', unsafe_allow_html=True)

# ---- 主界面渲染执行 ----
current_page = st.session_state.get('current_page', 'market')
render_args = PAGE_RENDER_ARGS.get(current_page, (L,))

_route(current_page, render_args)
