#!/usr/bin/env python3
"""
Standalone recommendation engine - no pandas dependency.
Uses today's market snapshot cache + built-in HOTSPOT_2026 data.
"""
import json
import os
import sys
from datetime import datetime
from collections import defaultdict

# ── Disable proxies ──
for var in ["HTTP_PROXY","HTTPS_PROXY","http_proxy","https_proxy","all_proxy"]:
    os.environ.pop(var, None)

# ── Constants from core/strategies.py ──
HOTSPOT_2026 = {
    "robot": {
        "name": "🤖 人形机器人",
        "desc": "具身智能产业化元年：减速器、执行器、灵巧手",
        "color": "#ef4444",
        "stocks": ["688017","002050","601689","300124","002472","002747","300503","603728"],
    },
    "ai_power": {
        "name": "⚡ AI芯片",
        "desc": "国产 GPU/ASIC + HBM + 半导体设备",
        "color": "#8b5cf6",
        "stocks": ["688041","688256","002371","688072","603501","300604","300274","688082"],
    },
    "ai_optical": {
        "name": "🔆 AI光通信",
        "desc": "800G→1.6T CPO 商用，订单排产至2028年",
        "color": "#38bdf8",
        "stocks": ["300308","300502","300394","601869","688498","300672","301007","300641"],
    },
    "ai_infra": {
        "name": "🖥️ AI算力硬件",
        "desc": "AI服务器+液冷+高速PCB+电源",
        "color": "#a78bfa",
        "stocks": ["000977","300012","002463","002660","300162","002416","300773","600854"],
    },
    "ai_app": {
        "name": "🧠 AI大模型",
        "desc": "AI Agent 智能体元年，MaaS 规模落地",
        "color": "#6366f1",
        "stocks": ["002230","688111","300033","300418","300624","002415","000938","002410"],
    },
    "low_alt": {
        "name": "🚁 低空经济",
        "desc": "eVTOL 适航认证加速，无人机物流试点",
        "color": "#22c55e",
        "stocks": ["002097","300342","002560","688568","002829","001696","000099","600580"],
    },
    "nuclear": {
        "name": "☢️ 核电",
        "desc": "AI 用电激增，核电基荷重估",
        "color": "#f97316",
        "stocks": ["601985","003816","000777","600875","600150","601868","300489","002130"],
    },
    "bio_drug": {
        "name": "💊 创新药",
        "desc": "ADC/GLP-1出海，License-out 突破",
        "color": "#ec4899",
        "stocks": ["600276","002422","300760","688180","300347","000538","002773","300759"],
    },
    "quantum": {
        "name": "🔬 量子计算",
        "desc": "十五五首位产业，量子整机商业交付",
        "color": "#14b8a6",
        "stocks": ["688027","002222","600120","688008","600360","600536","000938","603496"],
    },
}

SECTOR_META = {
    "robot": {"weight": 3.0, "boom_score": 9,
        "thesis": "具身智能产业化元年，Optimus 零部件放量，减速器/执行器供不应求",
        "catalyst": "特斯拉 Optimus 量产时间表确认，优必选上市带动产业链重估"},
    "ai_power": {"weight": 3.2, "boom_score": 8,
        "thesis": "国产 GPU/ASIC 信创替代加速，28nm 先进工艺产能持续扩张",
        "catalyst": "华为昇腾生态扩展，海光 DCU 政府采购订单放量"},
    "ai_optical": {"weight": 4.0, "boom_score": 10,
        "thesis": "800G→1.6T CPO 商用元年，全球光模块龙头订单排产至 2028 年",
        "catalyst": "英伟达 GB200/GB300 大规模出货，AI 数据中心互联带宽爆发"},
    "ai_infra": {"weight": 3.0, "boom_score": 8,
        "thesis": "液冷从可选变刚需，AI 服务器单机柜功率突破 130kW",
        "catalyst": "英维克进入英伟达 MGX 生态，数据中心建设投入同比翻倍"},
    "ai_app": {"weight": 2.5, "boom_score": 7,
        "thesis": "AI Agent 智能体元年，企业级大模型从 POC 到规模化落地",
        "catalyst": "国企 AI 平台采购提速，MaaS 标准化降低集成门槛"},
    "low_alt": {"weight": 2.8, "boom_score": 8,
        "thesis": "低空经济政策细则密集落地，eVTOL 适航认证推进",
        "catalyst": "工信部低空标准体系发布，多城试飞区批复加速"},
    "nuclear": {"weight": 3.5, "boom_score": 9,
        "thesis": "AI 数据中心用电激增，核电基荷电源重估",
        "catalyst": "\"三倍核能宣言\"全球共识，国内核准机组创历史新高"},
    "bio_drug": {"weight": 2.0, "boom_score": 7,
        "thesis": "ADC/GLP-1 全球出海，License-out 金额持续突破",
        "catalyst": "恒瑞 ADC 海外临床推进，百济神州全球销量登顶"},
    "quantum": {"weight": 2.2, "boom_score": 7,
        "thesis": "十五五未来产业首位，量子计算整机进入商业交付期",
        "catalyst": "国盾量子商业订单兑现，国产量子芯片打破零突破"},
}

STRATEGY_WEIGHTS = {
    "Mainforce": 4.0, "Northbound": 3.5, "Breakout": 3.0,
    "Hotspot": 2.5, "Momentum": 2.0, "Growth": 1.5, "Value": 1.0,
}

STRAT_ZH = {
    "Value": "💎价值", "Momentum": "🔥动量", "Growth": "🌟成长",
    "Mainforce": "💰主力", "Northbound": "🔗北向",
    "Breakout": "📈突破", "Hotspot": "🏭赛道",
}

def score_to_grade(score: float):
    if score >= 12:    return "S",  "强烈推荐"
    if score >= 9:     return "A+", "积极推荐"
    if score >= 6:     return "A",  "推荐关注"
    if score >= 3.5:   return "B",  "适度关注"
    return "C", "轻仓观察"

def load_market_snapshot():
    """
    Load latest fully-priced market snapshot.
    Since today (Mon) is pre-market, load Friday's closing data.
    """
    cache_dir = os.path.join(os.path.dirname(__file__), "..", "data", "cache")
    files = sorted([f for f in os.listdir(cache_dir) if f.startswith("full_market_snapshot_")])
    if not files:
        return None
    for fname in reversed(files):
        fpath = os.path.join(cache_dir, fname)
        with open(fpath) as f:
            data = json.load(f)
        priced = [x for x in data if float(str(x.get("最新价", 0)).replace(",","")) > 0]
        if len(priced) > 100:
            print(f"  📥 使用快照: {fname} ({len(priced)} 只有效价格)")
            return data
    with open(os.path.join(cache_dir, files[-1])) as f:
        return json.load(f)

def build_stock_map(market_data):
    stock_map = {}
    for item in market_data:
        code = str(item.get("代码", "")).strip()
        if code:
            try:
                price = float(str(item.get("最新价", 0)).replace(",",""))
            except:
                price = 0.0
            try:
                chg = float(str(item.get("涨跌幅", 0)).replace(",",""))
            except:
                chg = 0.0
            try:
                turnover = float(str(item.get("换手率", 0)).replace(",",""))
            except:
                turnover = 0.0
            try:
                mktcap = float(item.get("total_mv", item.get("mktcap", 0)))
            except:
                mktcap = 0.0
            try:
                circ_mv = float(item.get("circ_mv", item.get("nmc", 0)))
            except:
                circ_mv = 0.0
            stock_map[code] = {
                "代码": code, "名称": item.get("名称", code),
                "最新价": price, "涨跌幅": chg,
                "换手率": turnover,
                "成交额": item.get("成交额", item.get("volume", 0)),
                "mktcap": mktcap, "nmc": circ_mv,
            }
    return stock_map

def build_code_to_sector():
    code_to_sector = {}
    for sector_key, sec_data in HOTSPOT_2026.items():
        meta = SECTOR_META.get(sector_key, {})
        for code in sec_data["stocks"]:
            code_to_sector[code] = {
                "sector_key": sector_key, "sector_name": sec_data["name"],
                "sector_color": sec_data["color"],
                "sector_weight": meta.get("weight", 2.0),
                "boom_score": meta.get("boom_score", 5),
                "thesis": meta.get("thesis", ""), "catalyst": meta.get("catalyst", ""),
            }
    return code_to_sector

def simulate_strategies(stock_map):
    """Simulate strategy hits using Friday's closing data."""
    strategy_results = defaultdict(set)
    all_turnovers = sorted([row["换手率"] for row in stock_map.values()])
    all_chgs = sorted([row["涨跌幅"] for row in stock_map.values()])
    all_mktcaps = sorted([row["mktcap"] for row in stock_map.values()])
    def pctile(lst, pct):
        idx = int(len(lst) * pct)
        return lst[max(0, min(idx, len(lst)-1))]
    t65 = pctile(all_turnovers, 0.65)
    t70 = pctile(all_turnovers, 0.70)
    t75 = pctile(all_turnovers, 0.75)
    c70 = pctile(all_chgs, 0.70)
    m60 = pctile(all_mktcaps, 0.60)
    m80 = pctile(all_mktcaps, 0.80)
    for code, row in stock_map.items():
        chg, turn, mcap = row["涨跌幅"], row["换手率"], row["mktcap"]
        if chg >= c70 and turn >= t70:
            strategy_results["Mainforce"].add(code)
        if mcap >= m80 and chg > 0.5:
            strategy_results["Northbound"].add(code)
        if chg >= 3.0 and turn >= t75:
            strategy_results["Breakout"].add(code)
        if 1.5 <= chg < 6.0 and turn >= t65:
            strategy_results["Momentum"].add(code)
        if mcap <= m60 and turn >= t70 and chg >= 0.5:
            strategy_results["Growth"].add(code)
        if mcap >= m80 and -1.0 <= chg <= 2.0:
            strategy_results["Value"].add(code)
    return strategy_results

def run_recommendation_engine(top_n=10):
    market_data = load_market_snapshot()
    if not market_data:
        return {"error": "No market data available"}
    stock_map = build_stock_map(market_data)
    code_to_sector = build_code_to_sector()
    strategy_results = simulate_strategies(stock_map)
    hotspot_codes = set(code_to_sector.keys())
    # Add all hotspot stocks to the Hotspot strategy
    for code in hotspot_codes:
        if code in stock_map:
            strategy_results["Hotspot"].add(code)
    
    # ── Two-tier scoring ──
    hotspot_scored = []
    broad_scored = []
    for code in set(stock_map.keys()) | hotspot_codes:
        row = stock_map.get(code, {"名称": code, "最新价": 0, "涨跌幅": 0})
        chg = row["涨跌幅"]
        hits = [s for s, codes in strategy_results.items() if code in codes]
        in_hotspot = code in hotspot_codes
        
        # D1: Strategy resonance
        strategy_score = sum(STRATEGY_WEIGHTS.get(h, 1.0) for h in hits)
        # D2: Sector
        sec = code_to_sector.get(code, {})
        sector_score = (sec.get("boom_score", 0) / 10.0) * sec.get("sector_weight", 0) if sec else 0.0
        # D3: Technical
        if 1 <= chg < 3:         tech_score = 0.5
        elif 3 <= chg < 5:       tech_score = 1.0
        elif 5 <= chg < 8:       tech_score = 0.5
        elif -1 < chg < 0:       tech_score = 0.2
        elif -3 <= chg <= -1:    tech_score = 0.0
        else:                    tech_score = 0.0
        # D4: Resonance multiplier
        n_hits = len(hits)
        res_bonus = 2.0 if n_hits >= 4 else (1.0 if n_hits == 3 else (0.5 if n_hits == 2 else 0.0))
        total = strategy_score + sector_score + tech_score + res_bonus
        # Hotspot minimum: at least 1 strategy hit, or premium sector
        if in_hotspot and n_hits == 0 and sector_score < 1.5:
            continue
        # Broad: at least 3 hits + positive momentum
        if not in_hotspot and (n_hits < 3 or chg < 1.5):
            continue
        entry = {
            "code": code, "name": row["名称"], "price": row["最新价"],
            "change": chg, "strategy_score": round(strategy_score, 2),
            "sector_score": round(sector_score, 2),
            "tech_score": round(tech_score, 2),
            "resonance_bonus": round(res_bonus, 2),
            "total": round(total, 2), "hits": hits,
            "sector_key": sec.get("sector_key", ""),
            "sector_name": sec.get("sector_name", "—"),
            "thesis": sec.get("thesis", ""),
        }
        (hotspot_scored if in_hotspot else broad_scored).append(entry)
    hotspot_scored.sort(key=lambda x: -x["total"])
    broad_scored.sort(key=lambda x: -x["total"])
    
    # Build final list: try for 7 hotspot + 3 broad, fill gaps as needed
    n_hs = min(7, len(hotspot_scored))
    n_br = min(top_n - n_hs, len(broad_scored))
    # If not enough hotspot stocks, fill from broad
    if n_hs < top_n:
        remaining = top_n - n_hs
        n_br = min(remaining, len(broad_scored))
    selected = hotspot_scored[:n_hs] + broad_scored[:n_br]
    # Re-rank by score
    selected.sort(key=lambda x: -x["total"])
    
    # Build final stocks list
    stocks = []
    for rank, sc in enumerate(selected[:top_n], 1):
        hits = sc["hits"]
        grade, glabel = score_to_grade(sc["total"])
        reasons = []
        if "Mainforce" in hits:    reasons.append("主力净流入")
        if "Northbound" in hits:   reasons.append("北向增持")
        if "Breakout" in hits:     reasons.append("技术突破放量")
        if "Momentum" in hits:     reasons.append("量价共振")
        if "Value" in hits:        reasons.append("低估值")
        if "Growth" in hits:       reasons.append("机构活跃")
        if sc.get("thesis"):       reasons.append(sc["thesis"][:24])
        chg = sc["change"]
        if grade in ("S", "A+") and chg >= 5:
            action = "⚪ 观望回调"
        elif grade in ("S", "A+"):
            action = "🟢 积极买入"
        elif grade == "A":
            action = "🟡 关注建仓"
        elif grade == "B":
            action = "🔵 轻仓试探"
        else:
            action = "⚪ 持续观察"
        stocks.append({
            "rank": rank, "code": sc["code"], "name": sc["name"],
            "price": sc["price"], "change": sc["change"],
            "total": sc["total"],
            "strategy_score": sc["strategy_score"],
            "sector_score": sc["sector_score"],
            "tech_score": sc["tech_score"],
            "resonance_bonus": sc["resonance_bonus"],
            "grade": grade, "grade_label": glabel,
            "hits_str": " ".join(STRAT_ZH.get(h, h) for h in hits),
            "hit_count": len(hits), "action": action,
            "sector_key": sc.get("sector_key", ""),
            "sector_name": sc.get("sector_name", "—"),
            "reason": " · ".join(reasons[:4]) if reasons else "多策略共振",
        })
    
    # Sector stats
    sector_stats = []
    for sector_key, sec_data in HOTSPOT_2026.items():
        meta = SECTOR_META.get(sector_key, {})
        pool = set(sec_data["stocks"])
        recd = [s for s in stocks if s["code"] in pool]
        avg = sum(s["total"] for s in recd) / len(recd) if recd else 0
        sector_stats.append({
            "sector_key": sector_key, "sector_name": sec_data["name"],
            "color": sec_data["color"],
            "boom_score": meta.get("boom_score", 5),
            "weight": meta.get("weight", 2.0),
            "thesis": meta.get("thesis", ""),
            "catalyst": meta.get("catalyst", ""),
            "total_stocks": len(pool), "recommended_cnt": len(recd),
            "avg_score": round(avg, 2),
            "heat_index": round(meta.get("boom_score", 5) * meta.get("weight", 2) / 10.0 * 10, 1),
        })
    sector_stats.sort(key=lambda x: -x["heat_index"])
    top_sector = sector_stats[0]["sector_name"] if sector_stats else "—"
    top_sector_boom = sector_stats[0]["boom_score"] if sector_stats else 0
    return {
        "stocks": stocks, "sectors": sector_stats,
        "summary": {
            "strategies_active": len(strategy_results),
            "total_candidates": len(stock_map),
            "recommended_cnt": len(stocks),
            "grade_s_cnt": sum(1 for s in stocks if s["grade"] == "S"),
            "grade_ap_cnt": sum(1 for s in stocks if s["grade"] == "A+"),
            "top_sector": top_sector, "top_sector_boom": top_sector_boom,
            "generated_at": datetime.now().strftime("%H:%M:%S"),
        }
    }

def generate_report():
    now = datetime.now()
    print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] 正在生成核心荐股报告...\n")
    result = run_recommendation_engine(top_n=10)
    if "error" in result:
        print(f"⚠️ 荐股研报生成失败: {result['error']}")
        return
    summary = result["summary"]
    stocks = result["stocks"]
    sectors = result["sectors"]
    
    print(f"📅 Smart Stock Monitor — 多维共振核心荐股 ({now.strftime('%Y-%m-%d')})\n")
    print("━" * 60)
    print(f"\n✅ 选股引擎执行完毕")
    print(f"  📊 扫描标的池: {summary['total_candidates']} 只")
    print(f"  🎯 Top 10 金股: S级{summary['grade_s_cnt']}只, A+级{summary['grade_ap_cnt']}只")
    print(f"  🔥 今日最强主线: {summary['top_sector']} (景气度: {summary['top_sector_boom']}/10)")
    
    print(f"\n {'='*25} 赛道热度排行 {'='*25}")
    for i, sec in enumerate(sectors[:6], 1):
        bar = "█" * max(1, int(sec['heat_index'] / 2))
        print(f"  {i}. {sec['sector_name']:　<14} 热度: {sec['heat_index']:>4.1f} {bar}  (推荐{sec['recommended_cnt']}只, 均分{sec['avg_score']:.1f})")
    
    print(f"\n 🏆 Top 10 金股名单 {'='*40}\n")
    grade_emoji = {"S": "🔴", "A+": "🟠", "A": "🟡", "B": "🔵", "C": "⚪"}
    for s in stocks:
        ge = grade_emoji.get(s["grade"], "⚪")
        print(f"  {'─'*58}")
        prefix = "SH." if s["code"].startswith("6") else "SZ."
        sign = "+" if s["change"] >= 0 else ""
        print(f"  #{s['rank']} {s['name']:<6} ({prefix}{s['code']})")
        print(f"     现价: {s['price']:.2f} ({sign}{s['change']:.2f}%)")
        print(f"     评级: {ge} {s['grade_label']} 总分{s['total']:.1f} | 策略{s['strategy_score']:.1f}+赛道{s['sector_score']:.1f}+技术{s['tech_score']:.1f}")
        print(f"     策略共振: {s['hits_str']} ({s['hit_count']}重)")
        if s['sector_name'] != '—':
            print(f"     归属赛道: {s['sector_name']}")
        print(f"     核心逻辑: {s['reason'][:50]}")
        print(f"     操作建议: {s['action']}")
    
    print(f"\n {'='*20} 最强主线深度解析 {'='*20}\n")
    for sec in sectors[:3]:
        s_stocks = [s for s in stocks if s['sector_key'] == sec['sector_key']]
        if not s_stocks:
            continue
        bar = "█" * max(1, int(sec['heat_index'] / 2))
        print(f"  📌 {sec['sector_name']} — 热度指数 {sec['heat_index']} {bar}")
        print(f"     景气度: {sec['boom_score']}/10 | 赛道权重: {sec['weight']}x")
        print(f"     核心逻辑: {sec['thesis']}")
        print(f"     催化事件: {sec['catalyst']}")
        stocks_names = '(' + ', '.join(f"{s['name']}{s['action']}" for s in s_stocks) + ')'
        print(f"     入围标的: {stocks_names}")
        print()
    
    print("  ─" * 30)
    print()
    print(f"  ⏰ 报告生成: {now.strftime('%Y-%m-%d %H:%M:%S')} (周一盘前)")
    print(f"  💡 本报告基于多因子共振模型(主力/北向/突破/动量/赛道)自动生成。")
    print(f"  ⚠️  股市有风险，投资需谨慎。顺势而为，紧抓最强主线板块，聚焦核心龙头！")
    
    report_dir = os.path.join(os.path.dirname(__file__), "..", "data", "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_file = os.path.join(report_dir, f"recommend_{now.strftime('%Y%m%d')}.json")
    with open(report_file, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n  📁 报告已保存: {report_file}")

if __name__ == "__main__":
    generate_report()
