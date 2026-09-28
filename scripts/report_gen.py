import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


APP_ROOT = Path("/app")
CACHE_DIR = APP_ROOT / "data" / "cache"

if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(proxy_key, None)


def _trade_date_candidates(now: datetime) -> list[str]:
    days = []
    cursor = now
    for _ in range(8):
        if cursor.weekday() < 5:
            days.append(cursor.strftime("%Y-%m-%d"))
        cursor -= timedelta(days=1)
    return days


def _snapshot_path(date_text: str) -> Path:
    return CACHE_DIR / f"full_market_snapshot_{date_text}.json"


def _to_number(series_or_value):
    return pd.to_numeric(series_or_value, errors="coerce")


def _load_snapshot_from_file(now: datetime) -> tuple[pd.DataFrame, str, str]:
    for date_text in _trade_date_candidates(now):
        path = _snapshot_path(date_text)
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            df = pd.DataFrame(data)
            if not df.empty:
                return df, date_text, f"Tushare 快照缓存 {path.name}"
    return pd.DataFrame(), "", "未找到快照缓存"


def _normalize_tushare_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    rename_map = {
        "ts_code": "代码",
        "pct_chg": "涨跌幅",
        "close": "最新价",
        "vol": "成交量",
        "amount": "成交额",
        "pe": "市盈率",
        "pb": "市净率",
        "turnover_rate": "换手率",
    }
    df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)
    if "代码" in df.columns:
        df["代码"] = df["代码"].astype(str).str.replace(r"\.(SH|SZ|BJ)$", "", regex=True)
    for col in ["最新价", "涨跌幅", "成交量", "成交额", "市盈率", "市净率", "pe_ttm", "换手率", "total_mv", "circ_mv"]:
        if col in df.columns:
            df[col] = _to_number(df[col])
    return df


def _fetch_snapshot_from_tushare(now: datetime) -> tuple[pd.DataFrame, str, str]:
    try:
        from core.tushare_client import get_ts_client

        ts = get_ts_client()
        if not ts.available:
            return pd.DataFrame(), "", "Tushare token 不可用"
        snap = ts.get_daily_snapshot()
        if snap is None or snap.empty:
            return pd.DataFrame(), "", "Tushare daily_snapshot 返回空"

        trade_date = str(snap["trade_date"].dropna().astype(str).max()) if "trade_date" in snap.columns else now.strftime("%Y%m%d")
        date_text = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}" if len(trade_date) == 8 else now.strftime("%Y-%m-%d")
        df = _normalize_tushare_snapshot(snap)

        try:
            name_map = ts.get_name_map()
            if name_map and "名称" not in df.columns:
                df["名称"] = df["代码"].astype(str).map(name_map).fillna(df["代码"].astype(str))
        except Exception:
            pass

        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _snapshot_path(date_text).write_text(json.dumps(df.to_dict("records"), ensure_ascii=False), encoding="utf-8")
        return df, date_text, "Tushare 实时快照"
    except Exception as exc:
        return pd.DataFrame(), "", f"Tushare 快照获取失败：{exc}"


def load_market_snapshot() -> tuple[pd.DataFrame, str, str]:
    now = datetime.now()
    df, date_text, source = _load_snapshot_from_file(now)
    if not df.empty:
        return _normalize_tushare_snapshot(df), date_text, source
    return _fetch_snapshot_from_tushare(now)


def load_industry_map() -> dict[str, str]:
    try:
        from core.tushare_client import get_ts_client

        basic = get_ts_client().get_stock_basic()
        if basic is None or basic.empty or "symbol" not in basic.columns or "industry" not in basic.columns:
            return {}
        return dict(zip(basic["symbol"].astype(str), basic["industry"].fillna("未分类").astype(str)))
    except Exception:
        return {}


def format_amount_yi(value) -> str:
    if pd.isna(value):
        return "N/A"
    # Tushare amount unit is 千元.
    return f"{float(value) / 100000:.2f}亿"


def market_breadth_lines(df: pd.DataFrame) -> list[str]:
    pct = _to_number(df.get("涨跌幅", pd.Series(dtype=float))).dropna()
    if pct.empty:
        return ["⚠️ 涨跌统计暂缺"]
    up = int((pct > 0).sum())
    down = int((pct < 0).sum())
    flat = int((pct == 0).sum())
    avg = float(pct.mean())
    median = float(pct.median())
    limit_up = int((pct >= 9.8).sum())
    limit_down = int((pct <= -9.8).sum())
    tone = "偏强" if up > down * 1.2 else "偏弱" if down > up * 1.2 else "震荡"
    participation = up / max(up + down + flat, 1)
    action = "控制仓位，优先等修复" if tone == "偏弱" else "可围绕强势主线轻仓试错" if tone == "偏强" else "保持观察，等待方向选择"
    return [
        f"- 市场状态：**{tone}**，上涨 {up} 家，下跌 {down} 家，平盘 {flat} 家，上涨占比 {participation:.1%}。",
        f"- 平均涨跌幅：**{avg:.2f}%**，中位数：**{median:.2f}%**，涨停附近 {limit_up} 家，跌停附近 {limit_down} 家。",
        f"- 盘后动作：{action}。",
    ]


def hot_industry_lines(df: pd.DataFrame) -> list[str]:
    industry_map = load_industry_map()
    if industry_map:
        df = df.copy()
        df["行业"] = df["代码"].astype(str).map(industry_map).fillna("未分类")
    elif "行业" not in df.columns:
        return ["⚠️ 行业映射暂缺，无法生成 Tushare 行业热度排行。"]

    required = {"行业", "涨跌幅", "成交额"}
    if not required.issubset(df.columns):
        return ["⚠️ 行业热度字段暂缺。"]
    work = df.dropna(subset=["行业", "涨跌幅"]).copy()
    if work.empty:
        return ["⚠️ 行业热度样本暂缺。"]
    grouped = (
        work.groupby("行业")
        .agg(
            平均涨跌幅=("涨跌幅", "mean"),
            上涨家数=("涨跌幅", lambda s: int((s > 0).sum())),
            样本数=("涨跌幅", "count"),
            成交额=("成交额", "sum"),
        )
        .reset_index()
    )
    grouped = grouped[grouped["样本数"] >= 5].sort_values(["平均涨跌幅", "成交额"], ascending=False).head(5)
    if grouped.empty:
        return ["⚠️ 行业热度有效样本不足。"]
    lines = ["| 行业 | 平均涨跌幅 | 上涨家数 | 成交额 | 解读 |", "|---|---:|---:|---:|---|"]
    for _, row in grouped.iterrows():
        strength = "主线强" if row["平均涨跌幅"] > 1 else "相对抗跌" if row["平均涨跌幅"] > -1 else "弱修复"
        lines.append(f"| {row['行业']} | {row['平均涨跌幅']:.2f}% | {int(row['上涨家数'])}/{int(row['样本数'])} | {format_amount_yi(row['成交额'])} | {strength} |")
    return lines


def value_stock_lines(df: pd.DataFrame) -> list[str]:
    required = {"代码", "名称", "最新价", "涨跌幅", "市盈率", "市净率", "成交额"}
    if not required.issubset(df.columns):
        return ["⚠️ 估值字段暂缺，无法生成低 PE/PB 组合。"]
    work = df.copy()
    work["市盈率"] = _to_number(work["市盈率"])
    work["市净率"] = _to_number(work["市净率"])
    work["成交额"] = _to_number(work["成交额"])
    work = work[
        (work["市盈率"] > 0)
        & (work["市盈率"] < 10)
        & (work["市净率"] > 0)
        & (work["市净率"] < 1.0)
        & (work["成交额"] > 50_000)
    ].copy()
    if work.empty:
        return ["• 今日未筛出 PE < 10、PB < 1.0 且成交活跃的样本。"]
    work["估值得分"] = (1 / work["市盈率"]) + (1 / work["市净率"])
    top = work.sort_values(["估值得分", "成交额"], ascending=False).head(5)
    lines = ["| 标的 | PE | PB | 涨跌幅 | 成交额 | 观察点 |", "|---|---:|---:|---:|---:|---|"]
    for _, row in top.iterrows():
        watch = "估值低，等放量企稳" if row["涨跌幅"] < 0 else "估值低且有资金尝试"
        lines.append(f"| {row['名称']} ({row['代码']}) | {row['市盈率']:.1f} | {row['市净率']:.2f} | {row['涨跌幅']:.2f}% | {format_amount_yi(row['成交额'])} | {watch} |")
    return lines


def active_stock_lines(df: pd.DataFrame) -> list[str]:
    required = {"代码", "名称", "最新价", "涨跌幅", "成交额"}
    if not required.issubset(df.columns):
        return ["⚠️ 活跃股字段暂缺。"]
    work = df.copy()
    work["涨跌幅"] = _to_number(work["涨跌幅"])
    work["成交额"] = _to_number(work["成交额"])
    work = work[(work["涨跌幅"] > 1) & (work["涨跌幅"] < 9.8)].sort_values(["涨跌幅", "成交额"], ascending=False).head(5)
    if work.empty:
        return ["• 今日强势活跃样本暂缺。"]
    lines = ["| 标的 | 最新价 | 涨跌幅 | 成交额 | 备注 |", "|---|---:|---:|---:|---|"]
    for _, row in work.iterrows():
        note = "接近涨停，谨慎追高" if row["涨跌幅"] >= 8 else "强势活跃，观察持续性"
        lines.append(f"| {row['名称']} ({row['代码']}) | {row['最新价']:.2f} | {row['涨跌幅']:.2f}% | {format_amount_yi(row['成交额'])} | {note} |")
    return lines


def generate_report() -> str:
    print(f"[{datetime.now()}] 正在生成每日盘后研报...")
    df, trade_date, source = load_market_snapshot()
    if df.empty:
        return "\n".join(
            [
                f"📅 **每日股市研报 - {datetime.now().strftime('%Y-%m-%d')}**",
                "---",
                f"⚠️ Tushare 全市场快照不可用：{source}",
                "💡 *本报告由 Smart Stock Monitor 自动生成，仅供参考。*",
            ],
        )

    lines = [
        f"📅 **每日股市研报 - {trade_date or datetime.now().strftime('%Y-%m-%d')}**",
        f"数据来源：{source}，样本数 {len(df)} 只",
        "---",
        "## 一句话结论",
        market_breadth_lines(df)[0].replace("- 市场状态：", "今日 A 股"),
        "",
        "📈 **市场宽度**",
        *market_breadth_lines(df),
        "",
        "🔥 **Tushare 行业热度**",
        *hot_industry_lines(df),
        "",
        "🚀 **强势活跃股**",
        *active_stock_lines(df),
        "",
        "💎 **价值洼地提醒（低 PE/PB）**",
        *value_stock_lines(df),
        "",
        "## 明日观察",
        "- 若行业热度前排继续放量，优先观察相对抗跌且成交额扩大的方向。",
        "- 若市场宽度继续偏弱，避免扩大试错，等待指数和量能同步修复。",
        "",
        "---",
        "💡 *本报告由 Smart Stock Monitor 自动生成，仅供参考。*",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_report())
