"""
荐股引擎 v2.0 — SSM Quantum Pro
多策略共振 × 行业赛道深度整合 × 四维评分体系
"""
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════
#  2026 赛道元数据（权重 + 逻辑描述 + 景气度）
# ══════════════════════════════════════════════════════════════════
SECTOR_META = {
    "robot": {
        "weight": 3.0,
        "boom_score": 9,          # 景气度 /10
        "thesis": "具身智能产业化元年，Optimus 零部件放量，减速器/执行器供不应求",
        "catalyst": "特斯拉 Optimus 量产时间表确认，优必选上市带动产业链重估",
    },
    "ai_power": {
        "weight": 3.2,
        "boom_score": 8,
        "thesis": "国产 GPU/ASIC 信创替代加速，28nm 先进工艺产能持续扩张",
        "catalyst": "华为昇腾生态扩展，海光 DCU 政府采购订单放量",
    },
    "ai_optical": {
        "weight": 4.0,            # 最高权重 — 当前最强硬件主线
        "boom_score": 10,
        "thesis": "800G→1.6T CPO 商用元年，全球光模块龙头订单排产至 2028 年",
        "catalyst": "英伟达 GB200/GB300 大规模出货，AI 数据中心互联带宽爆发",
    },
    "ai_infra": {
        "weight": 3.0,
        "boom_score": 8,
        "thesis": "液冷从可选变刚需，AI 服务器单机柜功率突破 130kW",
        "catalyst": "英维克进入英伟达 MGX 生态，数据中心建设投入同比翻倍",
    },
    "ai_app": {
        "weight": 2.5,
        "boom_score": 7,
        "thesis": "AI Agent 智能体元年，企业级大模型从 POC 到规模化落地",
        "catalyst": "国企 AI 平台采购提速，MaaS 标准化降低集成门槛",
    },
    "low_alt": {
        "weight": 2.8,
        "boom_score": 8,
        "thesis": "低空经济政策细则密集落地，eVTOL 适航认证推进，无人机物流试点扩大",
        "catalyst": "工信部低空标准体系发布，多城试飞区批复加速",
    },
    "nuclear": {
        "weight": 3.5,
        "boom_score": 9,
        "thesis": "AI 数据中心用电激增，核电基荷电源重估，在建机组全球领先",
        "catalyst": "\"三倍核能宣言\"全球共识，国内核准机组数创历史新高",
    },
    "bio_drug": {
        "weight": 2.0,
        "boom_score": 7,
        "thesis": "ADC/GLP-1 全球出海，中国创新药 License-out 金额持续突破",
        "catalyst": "恒瑞 ADC 海外临床推进，百济神州泽布替尼全球销量登顶",
    },
    "quantum": {
        "weight": 2.2,
        "boom_score": 7,
        "thesis": "十五五未来产业首位，量子计算整机进入商业交付期",
        "catalyst": "国盾量子商业订单兑现，国产量子芯片打破零突破",
    },
}

# ── 策略权重 ────────────────────────────────────────────────────
STRATEGY_WEIGHTS = {
    "Mainforce":  4.0,   # 主力净流入 — 最强确定性信号
    "Northbound": 3.5,   # 北向外资定价锚
    "Breakout":   3.0,   # 技术突破 — 量价信号
    "Hotspot":    2.5,   # 热点赛道龙头（不含赛道额外分）
    "Momentum":   2.0,   # 动量趋势
    "Growth":     1.5,   # 成长活跃度
    "Value":      1.0,   # 价值底仓
}

# ── 评级 ────────────────────────────────────────────────────────
def _score_to_grade(score: float) -> tuple:
    if score >= 12:  return "S",  "强烈推荐", "#f43f5e"
    if score >= 9:   return "A+", "积极推荐", "#fb923c"
    if score >= 6:   return "A",  "推荐关注", "#f59e0b"
    if score >= 3.5: return "B",  "适度关注", "#10b981"
    return                  "C",  "轻仓观察", "#64748b"


# ══════════════════════════════════════════════════════════════════
#  主引擎
# ══════════════════════════════════════════════════════════════════
def run_recommendation_engine(top_n: int = 30) -> dict:
    """
    四维评分引擎：策略 × 赛道 × 技术 × 行业景气
    返回 dict:
      'stocks'  : pd.DataFrame   — 个股推荐列表
      'sectors' : pd.DataFrame   — 赛道热度统计
      'summary' : dict           — 市场摘要
    """
    from main import find_value_stocks, find_momentum_stocks, find_growth_stocks
    from core.strategies import (
        find_mainforce_stocks, find_northbound_top,
        find_tech_breakout, find_hotspot_stocks, HOTSPOT_2026
    )

    # ── Step 1: 构建赛道→股票反查表 ──────────────────────────────
    # code -> {sector_key, sector_name, sector_color, sector_weight, boom_score, thesis, catalyst}
    code_to_sector: dict[str, dict] = {}
    for sector_key, sec_data in HOTSPOT_2026.items():
        meta = SECTOR_META.get(sector_key, {})
        for code in sec_data.get("stocks", []):
            code_to_sector[code] = {
                "sector_key":    sector_key,
                "sector_name":   sec_data["name"],
                "sector_color":  sec_data["color"],
                "sector_weight": meta.get("weight", 2.0),
                "boom_score":    meta.get("boom_score", 5),
                "thesis":        meta.get("thesis", ""),
                "catalyst":      meta.get("catalyst", ""),
            }

    # ── Step 2: 运行所有策略 ──────────────────────────────────────
    strategy_results: dict[str, set[str]] = {}
    all_data: dict[str, dict] = {}

    fetchers = {
        "Value":      find_value_stocks,
        "Momentum":   find_momentum_stocks,
        "Growth":     find_growth_stocks,
        "Mainforce":  find_mainforce_stocks,
        "Northbound": find_northbound_top,
        "Breakout":   find_tech_breakout,
    }
    for name, fn in fetchers.items():
        try:
            df = fn()
            if df is None or df.empty:
                continue
            strategy_results[name] = set(df["代码"].astype(str))
            for _, row in df.iterrows():
                code = str(row["代码"])
                if code not in all_data:
                    all_data[code] = dict(row)
        except Exception as e:
            logger.warning(f"策略 {name} 失败: {e}")

    # 热点赛道（带板块字段）
    try:
        hdf = find_hotspot_stocks(None)
        if not hdf.empty:
            strategy_results["Hotspot"] = set(hdf["代码"].astype(str))
            for _, row in hdf.iterrows():
                code = str(row["代码"])
                if code not in all_data:
                    all_data[code] = dict(row)
    except Exception as e:
        logger.warning(f"热点赛道失败: {e}")

    # 确保热点赛道所有股票都被考虑（即使未被其他策略命中）
    for code in code_to_sector:
        if code not in all_data:
            all_data[code] = {"代码": code, "名称": code, "最新价": 0, "涨跌幅": 0}

    # ── Step 3: 四维评分 ─────────────────────────────────────────
    all_codes = set(all_data.keys())
    score_map: dict[str, dict] = {}

    for code in all_codes:
        row = all_data.get(code, {})
        chg = float(row.get("涨跌幅", 0) or 0)
        hits = [s for s, codes in strategy_results.items() if code in codes]

        # 维度1：策略共振分
        strategy_score = sum(STRATEGY_WEIGHTS.get(h, 1.0) for h in hits)

        # 维度2：赛道分（景气度 × 赛道权重）
        sec_info = code_to_sector.get(code, {})
        boom = sec_info.get("boom_score", 0)
        sec_weight = sec_info.get("sector_weight", 0)
        sector_score = (boom / 10.0) * sec_weight if sec_info else 0.0

        # 维度3：技术动量分
        if 1 <= chg < 3:
            tech_score = 0.5
        elif 3 <= chg < 5:
            tech_score = 1.0
        elif chg >= 5:
            tech_score = 0.5   # 追高风险
        elif -1 < chg < 0:
            tech_score = 0.2   # 轻微回调，正常
        else:
            tech_score = 0.0

        # 维度4：多策略共振乘数（命中策略越多，额外加成）
        if len(hits) >= 4:
            resonance_bonus = 2.0
        elif len(hits) == 3:
            resonance_bonus = 1.0
        elif len(hits) == 2:
            resonance_bonus = 0.5
        else:
            resonance_bonus = 0.0

        total = strategy_score + sector_score + tech_score + resonance_bonus

        # 最低门槛：至少有策略命中 OR 在核心赛道内且景气度高
        if total < 1.0:
            continue

        score_map[code] = {
            "strategy_score":  round(strategy_score, 2),
            "sector_score":    round(sector_score, 2),
            "tech_score":      round(tech_score, 2),
            "resonance_bonus": round(resonance_bonus, 2),
            "total":           round(total, 2),
            "hits":            hits,
        }

    # ── Step 4: 组装个股 DataFrame ───────────────────────────────
    STRAT_ZH = {
        "Value":      "💎价值", "Momentum": "🔥动量", "Growth": "🌟成长",
        "Mainforce":  "💰主力", "Northbound": "🔗北向",
        "Breakout":   "📈突破", "Hotspot": "🏭赛道",
    }

    sorted_codes = sorted(score_map, key=lambda c: -score_map[c]["total"])[:top_n]
    rows = []
    for rank, code in enumerate(sorted_codes, 1):
        sc   = score_map[code]
        row  = all_data.get(code, {})
        sec  = code_to_sector.get(code, {})
        hits = sc["hits"]
        grade, glabel, gcolor = _score_to_grade(sc["total"])

        # 荐股理由 — 结合赛道逻辑
        reasons = []
        if "Mainforce" in hits:
            reasons.append("主力净流入")
        if "Northbound" in hits:
            reasons.append("北向增持")
        if "Breakout" in hits:
            reasons.append("技术突破放量")
        if "Momentum" in hits:
            reasons.append("量价共振")
        if "Value" in hits:
            reasons.append("低估值")
        if "Growth" in hits:
            reasons.append("机构活跃")
        if sec.get("thesis"):
            reasons.append(sec["thesis"][:30])

        # 综合建议
        chg = float(row.get("涨跌幅", 0) or 0)
        if grade in ("S", "A+") and chg < 5:
            action = "🟢 积极买入"
        elif grade == "A":
            action = "🟡 关注建仓"
        elif grade == "B":
            action = "🔵 轻仓试探"
        else:
            action = "⚪ 持续观察"

        rows.append({
            "排名":     rank,
            "代码":     code,
            "名称":     row.get("名称", code),
            "最新价":   float(row.get("最新价", 0) or 0),
            "涨跌幅":   float(row.get("涨跌幅", 0) or 0),
            "总评分":   sc["total"],
            "策略分":   sc["strategy_score"],
            "赛道分":   sc["sector_score"],
            "技术分":   sc["tech_score"],
            "共振加成": sc["resonance_bonus"],
            "评级":     grade,
            "评级标签": glabel,
            "评级色":   gcolor,
            "命中策略": " ".join(STRAT_ZH.get(h, h) for h in hits),
            "命中数":   len(hits),
            "操作建议": action,
            "赛道键":   sec.get("sector_key", ""),
            "赛道名":   sec.get("sector_name", "—"),
            "赛道色":   sec.get("sector_color", "#64748b"),
            "景气度":   sec.get("boom_score", 0),
            "赛道逻辑": sec.get("thesis", ""),
            "催化剂":   sec.get("catalyst", ""),
            "荐股理由": " · ".join(reasons[:4]) if reasons else "多策略共振",
        })

    stocks_df = pd.DataFrame(rows)

    # ── Step 5: 赛道热度统计 ─────────────────────────────────────
    sector_stats = []
    for sector_key, sec_data in HOTSPOT_2026.items():
        meta = SECTOR_META.get(sector_key, {})
        pool = set(sec_data.get("stocks", []))
        recommended = [c for c in sorted_codes if c in pool]
        hit_by_strategy = sum(
            1 for c in pool
            if any(c in codes for codes in strategy_results.values())
        )
        avg_score = (
            sum(score_map[c]["total"] for c in recommended) / len(recommended)
            if recommended else 0
        )
        sector_stats.append({
            "sector_key":  sector_key,
            "sector_name": sec_data["name"],
            "color":       sec_data["color"],
            "boom_score":  meta.get("boom_score", 5),
            "weight":      meta.get("weight", 2.0),
            "thesis":      meta.get("thesis", ""),
            "catalyst":    meta.get("catalyst", ""),
            "total_stocks":    len(pool),
            "recommended_cnt": len(recommended),
            "strategy_hits":   hit_by_strategy,
            "avg_score":       round(avg_score, 2),
            "热度指数":        round(meta.get("boom_score", 5) * meta.get("weight", 2) / 10.0 * 10, 1),
        })
    sectors_df = pd.DataFrame(sector_stats).sort_values("热度指数", ascending=False)

    # ── Step 6: 市场摘要 ─────────────────────────────────────────
    strategies_active = len(strategy_results)
    total_candidates = len(all_codes)
    grade_s_cnt  = len([r for r in rows if r["评级"] == "S"])
    grade_ap_cnt = len([r for r in rows if r["评级"] == "A+"])
    top_sector   = sectors_df.iloc[0]["sector_name"] if not sectors_df.empty else "—"
    top_sector_boom = int(sectors_df.iloc[0]["boom_score"]) if not sectors_df.empty else 0

    summary = {
        "strategies_active":  strategies_active,
        "total_candidates":   total_candidates,
        "recommended_cnt":    len(rows),
        "grade_s_cnt":        grade_s_cnt,
        "grade_ap_cnt":       grade_ap_cnt,
        "top_sector":         top_sector,
        "top_sector_boom":    top_sector_boom,
        "generated_at":       datetime.now().strftime("%H:%M:%S"),
    }

    return {"stocks": stocks_df, "sectors": sectors_df, "summary": summary}
