import sys
import os
from datetime import datetime

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)
os.environ.pop("all_proxy", None)

# Add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ── Mock streamlit BEFORE any project code imports it ──
import types
import functools

class _StAttr:
    """Each streamlit attribute is this, callable as decorator and as instance."""
    def __init__(self, name='streamlit'):
        self._name = name
    def cache_data(self, ttl=60, show_spinner=False):
        def dec(f):
            @functools.wraps(f)
            def wrap(*a, **kw): return f(*a, **kw)
            return wrap
        return dec
    def __getattr__(self, name):
        if name == 'cache_data':
            return self.cache_data
        return _StAttr(name)
    def __call__(self, *args, **kwargs):
        return None
    # For decorator usage like @st.cache_data(...) and @st.cache_data
    def __enter__(self): return self
    def __exit__(self, *a): pass

_st_mod = types.ModuleType('streamlit')
_attr = _StAttr()
# Explicit common streamlit names
for _k in ['cache_data','spinner','empty','markdown','dataframe','columns','button',
           'text_input','selectbox','multiselect','slider','checkbox','radio',
           'sidebar','tabs','expander','container','info','success','warning',
           'error','exception','progress','balloons','snow','set_page_config',
           'title','header','subheader','write','metric','table','json','code',
           'latex','divider','caption','image','audio','video','altair_chart',
           'vega_lite_chart','plotly_chart','pyplot','map','line_chart','area_chart',
           'bar_chart','scatter_chart','session_state','query_params','secrets','config',
           'columns_config']:
    setattr(_st_mod, _k, _attr)
# Also set cache_data as a module-level shortcut that works
_st_mod.cache_data = _attr.cache_data
sys.modules['streamlit'] = _st_mod
# ── End streamlit mock ──

from core.recommender import run_recommendation_engine

def generate_report():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 正在生成核心荐股报告...")
    
    try:
        result = run_recommendation_engine(top_n=10)
        stocks_df = result.get("stocks")
        summary = result.get("summary", {})
        
        report = []
        report.append(f"📅 **Smart Stock Monitor - 核心荐股研报 ({datetime.now().strftime('%Y-%m-%d')})**")
        report.append("---")
        
        if stocks_df is None or stocks_df.empty:
            report.append("⚠️ 当前市场环境下，未匹配到符合所有安全边际与策略共振门槛的标的，建议多看少动。")
            return "\n".join(report)
            
        report.append(f"✅ **选股引擎执行完毕**")
        report.append(f"- 扫描标的池: {summary.get('total_candidates', 0)} 只")
        report.append(f"- 命中策略组: {summary.get('recommended_cnt', 0)} 只")
        report.append(f"- 当前最热主线: **{summary.get('top_sector', '无')}** (景气度评分: {summary.get('top_sector_boom', 0)})")
        report.append("\n🔥 **强力推荐金股 Top 10**")
        
        for idx, row in stocks_df.iterrows():
            rank = row.get('排名', idx+1)
            code = row.get('代码')
            name = row.get('名称')
            price = row.get('最新价', 0)
            change = row.get('涨跌幅', 0)
            grade = row.get('评级标签', row.get('评级', ''))
            score = row.get('总评分', 0)
            strategy = row.get('命中策略', '无')
            sector = row.get('赛道名', '—')
            reason = row.get('荐股理由', '')
            action = row.get('操作建议', '')
            
            report.append(f"**【{rank}】{name} ({code})** - 现价: {price:.2f} ({change:+.2f}%)")
            report.append(f"  ⭐ 评级: {grade} (总分: {score:.1f}) | 🎯 命中策略: {strategy}")
            report.append(f"  🏭 归属主线: {sector} | 💡 核心逻辑: {reason}")
            report.append(f"  👉 **建议: {action}**")
            report.append("")
            
        report.append("---")
        report.append("💡 *本报告基于多维因子共振模型自动生成，不对实际交易产生指导，股市有风险，投资需谨慎。*")
        
        return "\n".join(report)
        
    except Exception as e:
        import traceback
        return f"⚠️ 荐股研报生成失败: {e}\n{traceback.format_exc()}"

if __name__ == "__main__":
    content = generate_report()
    print(content)
