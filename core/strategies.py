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
    # ── 赛道 1：人形机器人 (具身智能元年) ─────────────────────
    "robot": {
        "name": "🤖 人形机器人",
        "desc": "具身智能产业化元年：减速器、执行器、灵巧手、力矩传感器、丝杠，深度绑定特斯拉 Optimus / 优必选",
        "color": "#ef4444",
        "stocks": [
            "688017",  # 绿的谐波 — 谐波减速器国产龙头
            "002050",  # 三花智控 — 执行器总成 / 热管理
            "601689",  # 拓普集团 — 直线执行器 / 灵巧手
            "300124",  # 汇川技术 — 伺服系统龙头
            "002472",  # 双环传动 — RV减速器
            "002747",  # 埃斯顿 — 六轴机器人整机
            "300503",  # 昊志机电 — 谐波减速器 + 电主轴
            "603728",  # 鸣志电器 — 步进/混合式电机
        ]
    },

    # ── 赛道 2a：AI 芯片算力 (国产替代 + 半导体设备) ───────────
    "ai_power": {
        "name": "⚡ AI芯片",
        "desc": "国产 GPU/ASIC + HBM 内存 + 半导体设备 — 国产算力替代浪潮加速，半导体自主可控核心逻辑",
        "color": "#8b5cf6",
        "stocks": [
            "688041",  # 海光信息 — 国产 CPU/GPU 领军，信创首选
            "688256",  # 寒武纪 — AI 推理芯片国产先锋
            "002371",  # 北方华创 — 刻蚀设备龙头，28nm+先进工艺
            "688072",  # 拓荆科技 — CVD/ALD 薄膜设备
            "603501",  # 韦尔股份 — CIS 图像传感芯片
            "300604",  # 长川科技 — 半导体测试设备
            "300274",  # 阳光电源 — 光存储/SiC 功率器件
            "688082",  # 中船汉光 — 光芯片封装
        ]
    },

    # ── 赛道 2b：AI 光通信 (2026 最强硬件主线，业绩兑现期) ─────
    "ai_optical": {
        "name": "🔆 AI光通信",
        "desc": "光模块 800G→1.6T 迭代、CPO 商用元年、光纤光缆量价齐升 — 订单排产至 2028 年，全球占60%份额",
        "color": "#38bdf8",
        "stocks": [
            "300308",  # 中际旭创 — 全球光模块绝对龙头，1.6T CPO 量产
            "300502",  # 新易盛 — 全球第二，LPO/CPO 双布局
            "300394",  # 天孚通信 — CPO 光引擎/光器件核心，高毛利壁垒
            "601869",  # 长飞光纤 — 全球光纤预制棒 #1，AI 基建底层
            "688498",  # 源杰科技 — 激光芯片 (光模块上游)
            "300672",  # 长光华芯 — 高功率激光芯片
            "301007",  # 晶盛机电 — 光模块封装测试设备
            "300641",  # 正弦电气 — 光模块结构件
        ]
    },

    # ── 赛道 2c：AI 算力硬件 (服务器 / 液冷散热) ────────────────
    "ai_infra": {
        "name": "🖥️ AI算力硬件",
        "desc": "AI 服务器 + 液冷散热 + 高速 PCB + 数据中心电源 — 算力军备竞赛全链受益",
        "color": "#a78bfa",
        "stocks": [
            "000977",  # 浪潮信息 — AI 服务器国内市占率 #1
            "300012",  # 英维克 — 液冷散热全栈龙头，进入英伟达 MGX 生态
            "002463",  # 沪电股份 — 高速 PCB，算力服务器核心材料
            "002660",  # 茂硕电源 — 数据中心电源
            "300162",  # 雷曼光电 — AI 服务器散热
            "002416",  # 爱施德 — AI 硬件分销 + 增值服务
            "300773",  # 拉普拉斯 — 热管理系统
            "600854",  # 春兰股份 — 液冷热交换器
        ]
    },

    # ── 赛道 2d：AI 应用 & 大模型 (Agent 智能体元年) ──────────
    "ai_app": {
        "name": "🧠 AI大模型",
        "desc": "AI Agent 智能体元年：大模型商业落地、MaaS 平台化、企业级 Agent 垂直 SaaS 重构",
        "color": "#f472b6",
        "stocks": [
            "002230",  # 科大讯飞 — 星火大模型 + Agent 工厂，国企深度渗透
            "688327",  # 云从科技 — AI 全栈，「晏清」合规大模型
            "300033",  # 同花顺 — AI 金融 Agent / 数据 SaaS 龙头
            "300413",  # 芒果超媒 — AIGC 内容生成，消费端最大流量入口
            "688298",  # 东方财富 — AI+金融数据平台
            "300418",  # 昆仑数据 — 企业级数据智能
            "002236",  # 大华股份 — AI 视觉应用，城市智能化
            "300454",  # 深信服 — AI 网络安全，零信任 Agent
        ]
    },

    # ── 赛道 3：低空经济 & 商业航天 (政策驱动万亿赛道) ────────
    "low_alt": {
        "name": "🛩️ 低空经济",
        "desc": "eVTOL 飞行汽车、无人机物流、低轨卫星组网、空管系统 — 政策细则密集落地",
        "color": "#3b82f6",
        "stocks": [
            "002085",  # 万丰奥威 — eVTOL 飞行汽车核心
            "688507",  # 纵横股份 — 工业无人机龙头
            "688665",  # 四创电子 — 空管雷达
            "000099",  # 中信海直 — 通用航空运营龙头
            "002900",  # 哈飞股份 — 直升机制造
            "300741",  # 华菱精工 — 无人机结构件
            "002097",  # 山河智能 — 通用航空设备
            "300489",  # 中飞股份 — 航空铝材
        ]
    },

    # ── 赛道 4：核电 & 电力能源 (AI 用电爆发，核电重估) ────────
    "nuclear": {
        "name": "☢️ 核电能源",
        "desc": "\"AI 的尽头是电力\" — 数据中心用电激增推动核电重估：运营商 + 装备制造 + 特高压",
        "color": "#10b981",
        "stocks": [
            "601985",  # 中国核电 — 国内核电运营双寡头
            "003816",  # 中国广核 — 全球第三大核电运营商
            "600875",  # 东方电气 — 核电主设备制造龙头
            "601727",  # 上海电气 — 核岛蒸汽发生器龙头
            "000777",  # 中核科技 — 核级阀门
            "300185",  # 格力博 — 核电辅助
            "600886",  # 国投电力 — 水核电综合运营
            "601668",  # 中国建筑 — 核电工程总承包
        ]
    },

    # ── 赛道 5：创新药 & 生物科技 (出海 + ADC 双主线) ─────────
    "bio_drug": {
        "name": "🧬 创新药",
        "desc": "ADC 抗体偶联药全球出海、GLP-1 减重药、PD-1/CAR-T — 中国创新药国际化提速",
        "color": "#f59e0b",
        "stocks": [
            "600276",  # 恒瑞医药 — 创新药龙头，ADC/GLP-1 双布局
            "688235",  # 百济神州 — 泽布替尼全球 top BTK
            "688180",  # 君实生物 — PD-1 出海
            "300347",  # 泰格医药 — CRO 临床龙头
            "300759",  # 康龙化成 — CDMO 全球化
            "688258",  # 荣昌生物 — ADC 国产先驱
            "688116",  # 天境生物 — CD47 靶点
            "300760",  # 迈瑞医疗 — 医疗器械龙头
        ]
    },

    # ── 赛道 6：量子科技 & 国产信创 (十五五战略产业) ──────────
    "quantum": {
        "name": "⚛️ 量子科技",
        "desc": "\"十五五\" 未来产业之首：量子计算整机交付、量子通信骨干网、国产算力信创替代",
        "color": "#06b6d4",
        "stocks": [
            "688027",  # 国盾量子 — A股量子科技标杆，量子计算+通信
            "600536",  # 中国软件 — 操作系统 + 信创基础软件
            "688041",  # 海光信息 — 国产算力信创替代
            "002230",  # 科大讯飞 — AI + 量子计算布局
            "688256",  # 寒武纪 — AI 推理芯片
            "300604",  # 长川科技 — 半导体测试设备
            "688168",  # 安博通 — 量子密钥分发 + 网络安全
            "688009",  # 中国通号 — 量子通信基础网络
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
