import functools
import os
import sys
import types
from datetime import datetime


for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(proxy_key, None)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class _StreamlitAttr:
    def cache_data(self, ttl=60, show_spinner=False):
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            return wrapper

        return decorator

    def __getattr__(self, _name):
        return self

    def __call__(self, *args, **kwargs):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


_streamlit = types.ModuleType("streamlit")
_attr = _StreamlitAttr()
for _name in [
    "cache_data",
    "spinner",
    "empty",
    "markdown",
    "dataframe",
    "columns",
    "button",
    "text_input",
    "selectbox",
    "multiselect",
    "slider",
    "checkbox",
    "radio",
    "sidebar",
    "tabs",
    "expander",
    "container",
    "info",
    "success",
    "warning",
    "error",
    "exception",
    "progress",
    "set_page_config",
    "title",
    "header",
    "subheader",
    "write",
    "metric",
    "table",
    "json",
    "caption",
    "session_state",
    "query_params",
    "secrets",
    "config",
]:
    setattr(_streamlit, _name, _attr)
_streamlit.cache_data = _attr.cache_data
sys.modules["streamlit"] = _streamlit

from core.recommender import run_recommendation_engine


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _normalize_action(action: str, change: float) -> str:
    text = str(action or "").strip()
    if not text:
        return "观察"
    if "买入" in text and change >= 7:
        return "高位观察"
    if "买入" in text:
        return "轻仓试错"
    return text


def _risk_level(change: float, score: float) -> str:
    if change >= 7:
        return "高"
    if score >= 10 and change < 4:
        return "中"
    return "中低"


def generate_report():
    now = datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 正在生成核心荐股报告...")

    try:
        result = run_recommendation_engine(top_n=10)
        stocks_df = result.get("stocks")
        summary = result.get("summary", {})

        report = [
            f"📅 **核心荐股观察 - {now.strftime('%Y-%m-%d')}**",
            "数据来源：Smart Stock Monitor 多维因子模型（Tushare 主链路）",
            "---",
        ]

        if stocks_df is None or stocks_df.empty:
            report.extend(
                [
                    "## 今日结论",
                    "⚠️ 未匹配到符合安全边际与策略共振门槛的标的。",
                    "- 操作：多看少动，不主动追高。",
                    "- 观察：等待主线和市场宽度重新共振。",
                ],
            )
            return "\n".join(report)

        total = summary.get("total_candidates", 0)
        count = summary.get("recommended_cnt", len(stocks_df))
        sector = summary.get("top_sector", "无")
        boom = summary.get("top_sector_boom", 0)
        top_row = stocks_df.iloc[0]
        top_name = top_row.get("名称", "未知")
        top_code = top_row.get("代码", "未知")

        report.extend(
            [
                "## 今日结论",
                f"- 扫描标的池：**{total}** 只；命中策略：**{count}** 只。",
                f"- 最热主线：**{sector}**，景气度评分 **{boom}**。",
                f"- 首位观察：**{top_name} ({top_code})**。若高开过急，等回踩承接，不追情绪尖点。",
                "",
                "## Top 10 观察池",
                "| 排名 | 标的 | 涨跌幅 | 评分 | 策略 | 主线 | 动作 | 风险 |",
                "|---:|---|---:|---:|---|---|---|---|",
            ],
        )

        for idx, row in stocks_df.iterrows():
            rank = row.get("排名", idx + 1)
            code = row.get("代码", "未知")
            name = row.get("名称", "未知")
            change = _safe_float(row.get("涨跌幅", 0))
            score = _safe_float(row.get("总评分", 0))
            strategy = str(row.get("命中策略", "无")).replace("|", "/")
            sector_name = str(row.get("赛道名", "—")).replace("|", "/")
            action = _normalize_action(str(row.get("操作建议", "")), change).replace("|", "/")
            risk = _risk_level(change, score)
            report.append(f"| {rank} | {name} ({code}) | {change:+.2f}% | {score:.1f} | {strategy} | {sector_name} | {action} | {risk} |")

        report.extend(
            [
                "",
                "## 执行纪律",
                "- 只把 Top 10 当作观察池，不把模型排序等同于买入指令。",
                "- 优先选择：主线明确、评分靠前、涨幅未过热、回踩有承接的标的。",
                "- 回避：涨幅过高、成交突然失真、主线退潮或指数弱修复失败的标的。",
                "- 单票试错仓位从小开始，跌破计划支撑先保护本金。",
                "",
                "---",
                "💡 *本报告自动生成，仅供研究参考，不构成投资建议。*",
            ],
        )

        return "\n".join(report)
    except Exception as exc:
        import traceback

        return f"⚠️ 荐股研报生成失败: {exc}\n{traceback.format_exc()}"


if __name__ == "__main__":
    print(generate_report())
