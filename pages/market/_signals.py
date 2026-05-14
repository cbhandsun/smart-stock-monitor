"""
技术信号计算层 — market 子包
_get_quick_signals: 单股轻量信号 (10min 缓存)
_batch_get_all_signals: 多线程并发批量信号
"""
import streamlit as st
import concurrent.futures


@st.cache_data(ttl=600, show_spinner=False)
def _get_quick_signals(code: str) -> dict:
    """
    轻量级技术信号 (缓存 10min) — 统一 DNA 引擎版
    """
    import numpy as np
    from modules.data_loader import fetch_kline
    from modules.quant import calculate_metrics, calculate_all_indicators
    from modules.analysis.dna_engine import get_dna_score
    from core.tushare_client import get_ts_client

    default = {
        'status': '—', 'buy': '—', 'sell': '—', 'action': '—',
        'action_short': '观望', 'rsi': 50, 'vol_ratio': 1.0,
        'score': 0, 'ma_pos': '—', 'macd_dir': '—', 'tags': [],
        'pe': 0, 'pb': 0,
    }
    try:
        full = ("sh" if code.startswith('6') else "sz") + code
        kline = fetch_kline(full, period='daily', datalen=100)
        if kline is None or kline.empty or len(kline) < 20:
            return default

        kline = calculate_all_indicators(kline)
        q_metrics = calculate_metrics(kline)

        latest = kline.iloc[-1]
        prev = kline.iloc[-2]
        close = float(latest['收盘'])
        prev_close = float(prev['收盘'])
        day_change = (close - prev_close) / prev_close * 100 if prev_close > 0 else 0

        vol = float(latest['成交量'])
        vol_avg5 = kline['成交量'].tail(5).mean()
        vol_ratio = round(vol / vol_avg5, 2) if vol_avg5 > 0 else 1.0

        score = get_dna_score(q_metrics, day_change, vol_ratio)

        if score >= 3:
            status = "看多 🚀"
            buy = "建议布局"
            action = "🟢 逢低加仓" if score >= 6 else "🔵 持有为主"
            action_short = "买入"
        elif score <= -3:
            status = "看空 📉"
            buy = "暂缓进场"
            action = "🔴 警惕风险" if score <= -6 else "⚪ 止盈避险"
            action_short = "卖出"
        else:
            status = "震荡 ↔️"
            buy = "观望"
            action = "🟡 箱体震荡"
            action_short = "观望"

        ma_pos = '多头' if q_metrics.get('ma_trend') == 'up' else '回调'
        macd_val = q_metrics.get('macd_hist', 0)
        macd_dir = '红轴' if macd_val > 0 else '绿轴'

        pe_val_db, pb_val_db = 0, 0
        ts = get_ts_client()
        if ts.available:
            basic = ts.get_daily_basic(code, limit=1)
            if basic is not None and not basic.empty:
                pe_val_db = float(basic.iloc[0].get('pe_ttm') or basic.iloc[0].get('pe') or 0)
                pb_val_db = float(basic.iloc[0].get('pb') or 0)

        # 分析标签
        tags = []
        rsi_val = q_metrics.get('rsi', 50)
        if score >= 5:    tags.append("💎 机构看好")
        elif score <= -5: tags.append("⚠️ 风险提示")
        if rsi_val <= 25:            tags.append("🔮 极度超卖(底部反转?)")
        elif 25 < rsi_val <= 30:    tags.append("🟢 RSI超卖(寻底)")
        elif rsi_val >= 80:         tags.append("🌪️ 极度超买(见顶风险)")
        elif 75 <= rsi_val < 80:    tags.append("🔴 RSI超买(高位)")
        if vol_ratio > 2.5:         tags.append("🌋 巨量爆发")
        elif vol_ratio > 1.5:       tags.append("🔥 放量突破")
        elif vol_ratio < 0.5:       tags.append("🧊 极致地量")
        elif vol_ratio < 0.7:       tags.append("❄️ 缩量洗盘")
        if day_change > 7:          tags.append("🚀 火箭发射")
        elif day_change > 3:        tags.append("📈 走势强劲")
        elif day_change < -7:       tags.append("🩸 瀑布下跌")
        elif day_change < -3:       tags.append("📉 弱势回调")
        if ma_pos == '多头':
            tags.append("🛡️ 均线多头(支撑强)")
        elif q_metrics.get('ma_trend') == 'down':
            tags.append("🥀 均线空头(阻力大)")
        if macd_dir == '红轴' and macd_val > 0.1:  tags.append("🐉 MACD强多头")
        elif macd_dir == '绿轴' and macd_val < -0.1: tags.append("🐻 MACD强空头")

        return {
            'status': status, 'buy': buy,
            'sell': '一般' if score > -3 else '风险',
            'action': action, 'action_short': action_short,
            'rsi': rsi_val, 'vol_ratio': vol_ratio, 'score': score,
            'ma_pos': ma_pos, 'macd_dir': macd_dir,
            'tags': tags[:8], 'pe': pe_val_db, 'pb': pb_val_db,
        }
    except Exception:
        return default


def _batch_get_all_signals(codes: list) -> dict:
    """多线程并发计算所有标的的实时信号 (加速秒开)"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_code = {executor.submit(_get_quick_signals, c): c for c in codes}
        for future in concurrent.futures.as_completed(future_to_code):
            c = future_to_code[future]
            try:
                results[c] = future.result()
            except Exception:
                results[c] = {
                    'tags': [], 'action_short': '观望',
                    'score': 0, 'vol_ratio': 1.0, 'action': '—',
                    'pe': 0, 'pb': 0,
                }
    return results
