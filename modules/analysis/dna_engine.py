import pandas as pd
import numpy as np
import re

def get_dna_score(q_metrics, day_change, vol_ratio):
    """
    计算综合 DNA 评分 (-10 ~ +10)
    """
    score = 0
    rsi = q_metrics.get('rsi', 50)
    kdj_k = q_metrics.get('kdj_k', 50)
    kdj_d = q_metrics.get('kdj_d', 50)
    bb_percent = q_metrics.get('bb_percent', 50)

    # RSI 信号
    if rsi < 30: score += 3
    elif rsi > 70: score -= 3

    # KDJ 信号
    if kdj_k > kdj_d and kdj_k < 40: score += 2
    elif kdj_k < kdj_d and kdj_k > 60: score -= 2

    # 量价配合
    if vol_ratio > 1.3 and day_change > 0: score += 2
    elif vol_ratio > 1.3 and day_change < -2: score -= 2

    # 布林位置
    if bb_percent < 15: score += 1
    elif bb_percent > 85: score -= 1

    # 趋势
    if day_change > 3: score += 1
    elif day_change < -3: score -= 1

    return score

def generate_tech_analysis(kline, q_metrics):
    """
    生成技术分析文本描述
    """
    if kline is None or kline.empty or len(kline) < 3:
        return [], [], [], []

    latest = kline.iloc[-1]
    prev = kline.iloc[-2]

    close_p = float(latest.get('收盘', 0))
    open_p = float(latest.get('开盘', 0))
    high_p = float(latest.get('最高', 0))
    low_p = float(latest.get('最低', 0))
    volume = float(latest.get('成交量', 0))
    prev_close = float(prev.get('收盘', 0))
    prev_volume = float(prev.get('成交量', 1))

    # 1. K线形态分析
    kline_analysis = []
    n_days = min(len(kline), 10)
    recent = kline.tail(n_days)
    recent_high = float(recent['最高'].max())
    recent_low = float(recent['最低'].min())
    high_date = recent.loc[recent['最高'].idxmax()].get('日期', '')
    
    day_change = (close_p - prev_close) / prev_close * 100 if prev_close > 0 else 0

    if recent_high > 0 and close_p < recent_high:
        drop_from_high = (recent_high - close_p) / recent_high * 100
        if drop_from_high > 3:
            h_str = str(high_date)[:10] if high_date else ''
            kline_analysis.append(f"从{h_str}高点 **¥{recent_high:.2f}** 跌至 ¥{close_p:.2f}，形成调整")

    if day_change > 3: kline_analysis.append(f"今日出现 **大幅反弹（+{day_change:.2f}%）**")
    elif day_change < -3: kline_analysis.append(f"今日 **大幅下挫（{day_change:.2f}%）**")
    else: kline_analysis.append(f"今日窄幅震荡（{day_change:+.2f}%）")

    vol_ratio = volume / prev_volume if prev_volume > 0 else 1.0
    if vol_ratio > 1.5: kline_analysis.append(f"量能 **显著放大**（量比 {vol_ratio:.1f}）")
    elif vol_ratio < 0.6: kline_analysis.append("成交量 **大幅萎缩**")

    # 2. 技术指标研判
    indicators = []
    rsi = q_metrics.get('rsi', 50)
    kdj_k = q_metrics.get('kdj_k', 50)
    kdj_d = q_metrics.get('kdj_d', 50)
    
    if rsi > 70: indicators.append(f"RSI **超买**（{rsi:.1f}）")
    elif rsi < 30: indicators.append(f"RSI **超卖**（{rsi:.1f}）")
    
    if kdj_k > kdj_d and kdj_k < 40: indicators.append("KDJ **低位金叉** 🟢")
    elif kdj_k < kdj_d and kdj_k > 60: indicators.append("KDJ **高位死叉** 🔴")

    # 3. 综合评分与建议
    score = get_dna_score(q_metrics, day_change, vol_ratio)
    
    if score >= 5: advice = "技术及量能极佳，趋势强劲，建议积极支撑位关注。"
    elif score >= 2: advice = "基本面稳健或形态处于改善过程中，可分批布局。"
    elif score <= -5: advice = "当前破位压力较大，建议空仓或大幅减持避险。"
    elif score <= -2: advice = "均线压制或持续缩量，短期建议以观望为主。"
    else: advice = "目前处于横盘或小幅震荡状态，耐心等待方向选择。"
    
    # 4. 关键价位
    price_levels = []
    for ma in ['MA5', 'MA20', 'MA60']:
        val = latest.get(ma)
        if pd.notna(val): price_levels.append(f"{ma}: ¥{float(val):.2f}")

    return kline_analysis, indicators, score, price_levels, advice
