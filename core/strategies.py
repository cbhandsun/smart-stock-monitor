"""
策略选股引擎
2026 热点赛道 + 主力吸筹 + 北向最爱 + 技术突破 + 概念热点
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Redis
try:
    from core.cache import RedisCache
    _redis = RedisCache()
    if not _redis.ping():
        _redis = None
except Exception:
    _redis = None


# ============================================================
#  2026 六大核心赛道
# ============================================================

HOTSPOT_2026 = {
    "robot": {
        "name": "🤖 人形机器人",
        "desc": "Tesla Bot 产业链：减速器、伺服电机、力矩传感器、灵巧手",
        "color": "#ef4444",
        "stocks": [
            "688017",  # 绿的谐波 — 谐波减速器龙头
            "300124",  # 汇川技术 — 伺服电机龙头
            "300607",  # 拓斯达 — 工业机器人
            "002747",  # 埃斯顿 — 六轴机器人
            "688218",  # 江苏北人 — 焊接机器人
            "002527",  # 新世纪 — 减速器
        ]
    },
    "low_alt": {
        "name": "🛩️ 低空经济",
        "desc": "eVTOL 飞行汽车、无人机物流、空管系统、低空基础设施",
        "color": "#3b82f6",
        "stocks": [
            "000099",  # 中信海直 — 通航龙头
            "002085",  # 万丰奥威 — eVTOL (飞行汽车)
            "688507",  # 纵横股份 — 工业无人机
            "002097",  # 山河智能 — 通用航空
            "300489",  # 中飞股份 — 航空铝材
            "688665",  # 四创电子 — 空管雷达
        ]
    },
    "ai_power": {
        "name": "⚡ AI算力",
        "desc": "GPU/ASIC 芯片、HBM 内存、光模块、AI 训练集群",
        "color": "#8b5cf6",
        "stocks": [
            "300308",  # 中际旭创 — 光模块龙头
            "688256",  # 寒武纪 — AI 芯片
            "688041",  # 海光信息 — 国产 CPU/GPU
            "002371",  # 北方华创 — 半导体设备
            "688072",  # 拓荆科技 — 薄膜沉积
            "603501",  # 韦尔股份 — CIS 芯片
        ]
    },
    "solid_bat": {
        "name": "🔋 固态电池",
        "desc": "全固态/半固态电池、固态电解质、锂金属负极",
        "color": "#10b981",
        "stocks": [
            "300750",  # 宁德时代 — 电池龙头
            "002460",  # 赣锋锂业 — 固态电池布局
            "300035",  # 中科电气 — 负极材料
            "688005",  # 容百科技 — 正极材料
            "300073",  # 当升科技 — 正极材料
            "002812",  # 恩捷股份 — 隔膜龙头
        ]
    },
    "bio_drug": {
        "name": "🧬 创新药",
        "desc": "ADC 抗体偶联、GLP-1 减重药、基因与细胞治疗",
        "color": "#f59e0b",
        "stocks": [
            "600276",  # 恒瑞医药 — 创新药龙头
            "688235",  # 百济神州 — PD-1/BTK
            "688180",  # 君实生物 — PD-1
            "300347",  # 泰格医药 — CRO
            "300759",  # 康龙化成 — CDMO
            "300529",  # 健帆生物 — 血液净化
        ]
    },
    "data_elem": {
        "name": "🌐 数据要素",
        "desc": "数据资产入表、数据交易、数字政府、隐私计算",
        "color": "#06b6d4",
        "stocks": [
            "300212",  # 易华录 — 数据湖
            "000032",  # 深桑达A — 数字政府
            "600536",  # 中国软件 — 操作系统
            "002410",  # 广联达 — 建筑数字化
            "300378",  # 鼎捷软件 — 工业数据
            "688168",  # 安博通 — 网络安全
        ]
    },
}


# ============================================================
#  策略函数
# ============================================================

def _get_ts():
    """获取 Tushare 客户端"""
    from core.tushare_client import get_ts_client
    return get_ts_client()


def find_hotspot_stocks(sector_key: str = None) -> pd.DataFrame:
    """
    2026 热点赛道选股 (5分钟缓存)
    sector_key: None=全部, 'robot'/'low_alt'/'ai_power'/...
    """
    cache_key = f"strat:hotspot:{sector_key or 'all'}"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    if sector_key and sector_key in HOTSPOT_2026:
        sectors = {sector_key: HOTSPOT_2026[sector_key]}
    else:
        sectors = HOTSPOT_2026

    from main import get_stock_names_batch
    from modules.data_loader import fetch_quotes_concurrent

    all_symbols = []
    symbol_sector = {}
    for key, data in sectors.items():
        for s in data["stocks"]:
            all_symbols.append(s)
            symbol_sector[s] = data["name"]

    if not all_symbols:
        return pd.DataFrame()

    name_map = get_stock_names_batch(all_symbols)
    live_quotes = fetch_quotes_concurrent(all_symbols)

    rows = []
    for sym in all_symbols:
        q = live_quotes.get(sym, {})
        rows.append({
            "代码": sym,
            "名称": name_map.get(sym, sym),
            "最新价": q.get("price", 0),
            "涨跌幅": q.get("change_pct", 0),
            "板块": symbol_sector.get(sym, ""),
        })

    df = pd.DataFrame(rows)
    if not df.empty and _redis:
        _redis.set(cache_key, df, expire=300)
    return df


def find_mainforce_stocks() -> pd.DataFrame:
    """
    主力吸筹策略: 连续3日主力(超大单+大单)净流入 > 0
    """
    cache_key = "strat:mainforce"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    ts = _get_ts()
    if not ts.available:
        return pd.DataFrame()

    try:
        # 获取最近交易日的全市场资金流
        results = []
        for i in range(5):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            ts._rate_limit()
            try:
                mf = ts.pro.moneyflow(trade_date=d,
                    fields='ts_code,trade_date,buy_elg_vol,sell_elg_vol,buy_lg_vol,sell_lg_vol,net_mf_vol')
                if mf is not None and not mf.empty:
                    results.append(mf)
                    if len(results) >= 3:
                        break
            except Exception:
                continue

        if len(results) < 3:
            return pd.DataFrame()

        # 合并3日数据
        combined = pd.concat(results, ignore_index=True)
        combined['net_big'] = (
            combined['buy_elg_vol'].astype(float) - combined['sell_elg_vol'].astype(float) +
            combined['buy_lg_vol'].astype(float) - combined['sell_lg_vol'].astype(float)
        )

        # 找连续3日净流入的股票
        dates = combined['trade_date'].unique()
        if len(dates) < 3:
            return pd.DataFrame()

        date_sets = []
        for d in sorted(dates)[-3:]:
            day_data = combined[combined['trade_date'] == d]
            inflow = set(day_data[day_data['net_big'] > 0]['ts_code'].tolist())
            date_sets.append(inflow)

        # 交集: 连续3日都在净流入
        consistent = date_sets[0]
        for s in date_sets[1:]:
            consistent = consistent & s

        if not consistent:
            return pd.DataFrame()

        # 取净流入最大的 top 15
        latest = results[0]
        latest['net_big'] = (
            latest['buy_elg_vol'].astype(float) - latest['sell_elg_vol'].astype(float) +
            latest['buy_lg_vol'].astype(float) - latest['sell_lg_vol'].astype(float)
        )
        candidates = latest[latest['ts_code'].isin(consistent)].copy()
        candidates = candidates.sort_values('net_big', ascending=False).head(15)

        # 获取名称和行情
        name_map = ts.get_name_map()
        rows = []
        for _, row in candidates.iterrows():
            code = row['ts_code'].split('.')[0]
            rows.append({
                "代码": code,
                "名称": name_map.get(code, code),
                "最新价": 0,
                "涨跌幅": 0,
                "主力净流入": f"{row['net_big']/10000:.0f}万手",
            })

        df = pd.DataFrame(rows)
        if not df.empty and _redis:
            _redis.set(cache_key, df, expire=300)
        return df
    except Exception as e:
        logger.error(f"主力吸筹策略失败: {e}")
        return pd.DataFrame()


def find_northbound_top() -> pd.DataFrame:
    """
    北向最爱: 陆股通十大成交股
    """
    cache_key = "strat:northbound"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    ts = _get_ts()
    if not ts.available:
        return pd.DataFrame()

    try:
        # 尝试最近5天找到数据
        for i in range(5):
            d = (datetime.now() - timedelta(days=i)).strftime('%Y%m%d')
            ts._rate_limit()
            try:
                df = ts.pro.hsgt_top10(trade_date=d, market_type='1')  # 沪股通
                df2 = ts.pro.hsgt_top10(trade_date=d, market_type='3')  # 深股通
                if df is not None and not df.empty:
                    break
            except Exception:
                df = None
                df2 = None
                continue

        frames = []
        if df is not None and not df.empty:
            frames.append(df)
        if df2 is not None and not df2.empty:
            frames.append(df2)

        if not frames:
            return pd.DataFrame()

        combined = pd.concat(frames, ignore_index=True)

        name_map = ts.get_name_map()
        rows = []
        for _, row in combined.iterrows():
            code = row['ts_code'].split('.')[0]
            net_buy = float(row.get('amount', 0) or 0)
            rows.append({
                "代码": code,
                "名称": row.get('name', name_map.get(code, code)),
                "最新价": float(row.get('close', 0) or 0),
                "涨跌幅": float(row.get('pct_change', 0) or 0),
                "净买入(亿)": f"{net_buy/1e4:.2f}" if net_buy else "0",
            })

        result = pd.DataFrame(rows)
        if not result.empty and _redis:
            _redis.set(cache_key, result, expire=300)
        return result
    except Exception as e:
        logger.error(f"北向最爱策略失败: {e}")
        return pd.DataFrame()


def find_tech_breakout() -> pd.DataFrame:
    """
    技术突破策略: MA5 上穿 MA20 (金叉) + 放量 (量>5日均量*1.5)
    从全市场 Tushare 数据中扫描
    """
    cache_key = "strat:tech_breakout"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    ts = _get_ts()
    if not ts.available:
        return pd.DataFrame()

    try:
        # 获取今日行情
        snap = ts.get_daily_snapshot()
        if snap is None or snap.empty:
            return pd.DataFrame()

        # 取涨幅 1~8% 且成交量靠前的候选
        snap['pct_chg'] = pd.to_numeric(snap['pct_chg'], errors='coerce')
        snap['vol'] = pd.to_numeric(snap['vol'], errors='coerce')
        candidates = snap[
            (snap['pct_chg'] > 1) & (snap['pct_chg'] < 8) &
            (snap['vol'] > 0)
        ].sort_values('vol', ascending=False).head(50)

        if candidates.empty:
            return pd.DataFrame()

        name_map = ts.get_name_map()
        breakout_stocks = []

        for _, row in candidates.head(30).iterrows():
            code = row['ts_code'].split('.')[0]
            try:
                # 获取近30日日线检查金叉
                kline = ts.get_daily(code, limit=30)
                if kline is None or len(kline) < 20:
                    continue

                # MA5 > MA20 且前一日 MA5 < MA20 (金叉)
                if 'MA5' in kline.columns and 'MA20' in kline.columns:
                    latest = kline.iloc[-1]
                    prev = kline.iloc[-2]
                    ma5_now = float(latest.get('MA5', 0) or 0)
                    ma20_now = float(latest.get('MA20', 0) or 0)
                    ma5_prev = float(prev.get('MA5', 0) or 0)
                    ma20_prev = float(prev.get('MA20', 0) or 0)

                    if ma5_now > ma20_now and ma5_prev <= ma20_prev:
                        # 确认放量
                        vol_avg = kline['成交量'].tail(5).mean()
                        vol_now = float(latest.get('成交量', 0) or 0)
                        if vol_now > vol_avg * 1.3:
                            breakout_stocks.append({
                                "代码": code,
                                "名称": name_map.get(code, code),
                                "最新价": float(latest.get('收盘', 0) or 0),
                                "涨跌幅": float(row.get('pct_chg', 0) or 0),
                                "信号": f"金叉+放量{vol_now/vol_avg:.1f}x",
                            })
            except Exception:
                continue

            if len(breakout_stocks) >= 10:
                break

        result = pd.DataFrame(breakout_stocks)
        if not result.empty and _redis:
            _redis.set(cache_key, result, expire=600)
        return result
    except Exception as e:
        logger.error(f"技术突破策略失败: {e}")
        return pd.DataFrame()


def find_concept_hot() -> pd.DataFrame:
    """
    概念热点: 获取 Tushare 概念板块列表供用户选择
    """
    ts = _get_ts()
    if not ts.available:
        return pd.DataFrame()

    cache_key = "strat:concept_list"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    df = ts.get_concept_list()
    if df is not None and not df.empty and _redis:
        _redis.set(cache_key, df, expire=3600)
    return df if df is not None else pd.DataFrame()


def find_concept_stocks_detail(concept_id: str, concept_name: str = '') -> pd.DataFrame:
    """获取概念板块成分股 + 实时行情"""
    ts = _get_ts()
    if not ts.available:
        return pd.DataFrame()

    cache_key = f"strat:concept:{concept_id}"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached

    try:
        detail = ts.get_concept_stocks(concept_id)
        if detail is None or detail.empty:
            return pd.DataFrame()

        codes = [c.split('.')[0] for c in detail['ts_code'].tolist()[:20]]
        name_map = ts.get_name_map()

        from modules.data_loader import fetch_quotes_concurrent
        quotes = fetch_quotes_concurrent(codes)

        rows = []
        for code in codes:
            q = quotes.get(code, {})
            rows.append({
                "代码": code,
                "名称": name_map.get(code, code),
                "最新价": q.get("price", 0),
                "涨跌幅": q.get("change_pct", 0),
                "板块": concept_name,
            })

        df = pd.DataFrame(rows)
        if not df.empty and _redis:
            _redis.set(cache_key, df, expire=300)
        return df
    except Exception as e:
        logger.error(f"概念成分股获取失败: {e}")
        return pd.DataFrame()
