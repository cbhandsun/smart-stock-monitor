"""
美股联动与产业链传导分析模块 — SSM Quantum Pro
计算美股及全球宏观因子对 A 股各大行业板块的传导得分 (USTransmissionPremium)
"""
import logging
from typing import Dict, Any, List

from utils.global_market_data import get_global_realtime_data

logger = logging.getLogger(__name__)


# ── 美股行业龙头/指数对 A 股板块的映射关系 ─────────────────────────────
# 对应 A股核心赛道 (core.recommender.SECTOR_META 的 keys):
# robot, ai_power, ai_optical, ai_infra, ai_app, low_alt, nuclear, bio_drug, quantum
US_A_SECTOR_MAPPING = {
    "robot": {
        "us_proxies": ["gb_dji"],  # 特斯拉/工业指数
        "desc": "特斯拉 Optimus 量产进展与美股机器人板块映射",
        "coef": 0.4  # 传导系数
    },
    "ai_power": {
        "us_proxies": ["费城半导体SOX", "gb_ixic"],
        "desc": "Nvidia/AMD 等 GPU 龙头走势及半导体设备传导",
        "coef": 0.6
    },
    "ai_optical": {
        "us_proxies": ["费城半导体SOX", "gb_ixic"],
        "desc": "英伟达 GB200 光互联与 CPO/光模块产业链映射",
        "coef": 0.7
    },
    "ai_infra": {
        "us_proxies": ["gb_ixic"],  # 液冷/服务器 (英维克, 工业富联等)
        "desc": "美股 AI 服务器与液冷散热 (Vertiv/SMCI) 传导",
        "coef": 0.5
    },
    "ai_app": {
        "us_proxies": ["gb_ixic"],  # 微软/Palantir
        "desc": "美股 AI 软件/Agent (Microsoft/PLTR) 产业落地映射",
        "coef": 0.4
    },
    "low_alt": {
        "us_proxies": ["gb_dji"],  # Joby/eVTOL 概念
        "desc": "美股 eVTOL 先驱 (Joby/Archer) 估值映射",
        "coef": 0.3
    },
    "nuclear": {
        "us_proxies": ["gb_inx"],  # 标普电力股 (CEG/VST)
        "desc": "美股核电/公用事业重估 (Constellation) 映射",
        "coef": 0.3
    },
    "quantum": {
        "us_proxies": ["gb_ixic"],
        "desc": "美股量子计算概念估值传导",
        "coef": 0.3
    },
    "bio_drug": {
        "us_proxies": ["gb_inx"],  # 美股创新药/礼来/诺和诺德
        "desc": "美股 GLP-1/ADC 龙头 (礼来/诺和诺德) 估值溢价",
        "coef": 0.4
    }
}


def calculate_us_transmission_premiums() -> Dict[str, Any]:
    """
    计算并输出全球宏观/美股对各 A 股板块的传导溢价得分
    返回格式：
      {
        "sectors": {
           "ai_optical": {"score": 1.2, "reason": "美股费城半导体大涨 2.4% 映射传导..."},
           ...
        },
        "market_sentiment": {
           "score": 0.5,
           "reason": "隔夜美股纳斯达克上涨 1.6%，开盘情绪偏多。"
        },
        "risk_discount": -0.2, # 恐慌指数 VIXY 变化折价
        "fx_discount": -0.1,    # 人民币汇率波动折价
      }
    """
    rt_data = get_global_realtime_data()
    
    premiums = {
        "sectors": {},
        "market_sentiment": {"score": 0.0, "reason": "全球市场表现平稳"},
        "risk_discount": 0.0,
        "fx_discount": 0.0
    }
    
    if not rt_data:
        logger.warning("No global realtime data available for US transmission calculation.")
        return premiums
    
    # ---- 1. 全球风险折价 (VIXY) ----
    if "恐慌指数VIXY" in rt_data:
        vixy_chg = rt_data["恐慌指数VIXY"]["change_pct"]
        # 如果 VIXY 大涨，说明全球恐慌情绪上升，压制风险偏好
        if vixy_chg > 2.0:
            # 每上涨 2%，扣 0.1 分，上限 -1.0 分
            raw_discount = -(vixy_chg / 2.0) * 0.1
            premiums["risk_discount"] = round(max(raw_discount, -1.0), 2)
        elif vixy_chg < -2.0:
            # 恐慌下行，微幅加分，上限 +0.3 分
            raw_bonus = -(vixy_chg / 2.0) * 0.05
            premiums["risk_discount"] = round(min(raw_bonus, 0.3), 2)

    # ---- 2. 人民币汇率折价 (USD/CNH) ----
    if "离岸人民币" in rt_data:
        fx_chg = rt_data["离岸人民币"]["change_pct"]
        # USD/CNH 上涨代表人民币贬值，资本流出 A股，负面冲击
        # 每贬值 0.2%，扣 0.2 分，上限 -1.0 分
        if fx_chg > 0.05:
            raw_fx_discount = -(fx_chg / 0.1) * 0.15
            premiums["fx_discount"] = round(max(raw_fx_discount, -1.0), 2)
        elif fx_chg < -0.05:
            # 人民币升值，加分，上限 +0.5 分
            raw_fx_bonus = -(fx_chg / 0.1) * 0.1
            premiums["fx_discount"] = round(min(raw_fx_bonus, 0.5), 2)

    # ---- 3. A股开盘情绪传导 (Nasdaq + SPX 隔夜表现) ----
    nasdaq_chg = rt_data.get("纳斯达克", {}).get("change_pct", 0.0)
    spx_chg = rt_data.get("标普500", {}).get("change_pct", 0.0)
    
    avg_us_chg = (nasdaq_chg + spx_chg) / 2.0
    if abs(avg_us_chg) > 0.3:
        # 每涨跌 1% 影响 0.4 分，上限 ±1.2 分
        sent_score = avg_us_chg * 0.4
        sent_score = max(min(sent_score, 1.2), -1.2)
        direction = "上扬" if avg_us_chg > 0 else "走弱"
        premiums["market_sentiment"] = {
            "score": round(sent_score, 2),
            "reason": f"隔夜美股纳斯达克及标普平均{direction} {abs(avg_us_chg):.2f}%，开盘情绪指数对应修正。"
        }

    # ---- 4. 行业板块映射溢价 (Sector Transmission) ----
    for sector_key, config in US_A_SECTOR_MAPPING.items():
        proxies = config["us_proxies"]
        coef = config["coef"]
        
        # 提取相关美股指数/龙头的涨跌幅
        changes = []
        for p in proxies:
            if p in rt_data:
                changes.append(rt_data[p]["change_pct"])
        
        if not changes:
            # 默认无溢价
            premiums["sectors"][sector_key] = {"score": 0.0, "reason": "无美股映射输入"}
            continue
            
        avg_proxy_chg = sum(changes) / len(changes)
        
        # 计算溢价分 = 均值涨跌幅 * 传导系数，限制在 [-1.5, +1.8] 分之间
        score = avg_proxy_chg * coef
        score = max(min(score, 1.8), -1.5)
        
        reasons = []
        for p in proxies:
            if p in rt_data:
                reasons.append(f"{p} {rt_data[p]['change_pct']:+.2f}%")
        
        desc = " · ".join(reasons)
        action = "溢价加成" if score >= 0 else "折价扣减"
        
        premiums["sectors"][sector_key] = {
            "score": round(score, 2),
            "reason": f"联动美股 ({desc})，{action} {abs(score):.2f} 分 ({config['desc']})"
        }
        
    return premiums
