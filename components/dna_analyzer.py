import streamlit as st
import plotly.graph_objects as go
import os
import datetime

from main import get_stock_names_batch, generate_ai_report
from modules.data_loader import fetch_kline, fetch_trading_signals, fetch_research_reports
from pages import save_watchlist, load_cached_report, REPORT_DIR

# conditional imports
try:
    from modules.fundamentals import get_financial_health_score
    from modules.quant import calculate_metrics, calculate_all_indicators
    from utils.charts import create_candlestick_chart
    from utils.tv_charts import render_tv_chart
except ImportError:
    get_financial_health_score = None
    calculate_metrics = None
    calculate_all_indicators = None
    create_candlestick_chart = None
    render_tv_chart = None


def _render_daily_info(full_symbol, stock_name):
    """渲染当日基本信息面板 — Sina 实时行情 (Redis 缓存 30s)"""
    import requests
    try:
        # Redis 单例
        _rc = getattr(_render_daily_info, '_rc', None)
        if _rc is None:
            try:
                from core.cache import RedisCache
                _rc = RedisCache()
                _render_daily_info._rc = _rc if _rc.ping() else None
                _rc = _render_daily_info._rc
            except Exception:
                _render_daily_info._rc = False
                _rc = None

        cache_key = f"quote:daily:{full_symbol}"
        quote = None
        if _rc:
            quote = _rc.get(cache_key)

        if not quote:
            url = f"https://hq.sinajs.cn/list={full_symbol}"
            headers = {'Referer': 'https://finance.sina.com.cn/'}
            r = requests.get(url, headers=headers, timeout=5)
            raw = r.text.strip()
            if '="' not in raw or raw.endswith('=""'):
                return
            parts = raw.split('="')[1].strip('"').split(',')
            if len(parts) < 32:
                return
            quote = {
                'name': parts[0],
                'open': float(parts[1] or 0),
                'prev_close': float(parts[2] or 0),
                'price': float(parts[3] or 0),
                'high': float(parts[4] or 0),
                'low': float(parts[5] or 0),
                'volume': float(parts[8] or 0),
                'amount': float(parts[9] or 0),
            }
            pc = quote['prev_close']
            pr = quote['price']
            if pc > 0 and pr > 0:
                quote['change_pct'] = (pr - pc) / pc * 100
                quote['change_amt'] = pr - pc
                quote['amplitude'] = (quote['high'] - quote['low']) / pc * 100
            else:
                quote['change_pct'] = quote['change_amt'] = quote['amplitude'] = 0
            if _rc:
                _rc.set(cache_key, quote, expire=30)

        # 渲染
        price = quote['price']
        if price <= 0:
            return
        chg_pct = quote['change_pct']
        chg_amt = quote['change_amt']
        color = "#ef4444" if chg_pct >= 0 else "#10b981"
        arrow = "▲" if chg_pct >= 0 else "▼"
        vol_wan = quote['volume'] / 10000
        amt_yi = quote['amount'] / 1e8

        st.markdown(f'''<div style="
            display:flex; align-items:center; gap:16px; padding:10px 16px;
            background:rgba(30,41,59,0.4); backdrop-filter:blur(12px);
            border:1px solid rgba(255,255,255,0.06); border-radius:12px; margin:6px 0 10px;
            flex-wrap:wrap;">
    <div style="display:flex; align-items:baseline; gap:8px;">
        <span style="font-family:'Outfit',sans-serif; font-size:1.6rem; font-weight:700; color:{color};">¥{price:.2f}</span>
        <span style="color:{color}; font-size:0.9rem; font-weight:600;">{arrow}{abs(chg_amt):.2f} ({chg_pct:+.2f}%)</span>
    </div>
    <div style="display:flex; gap:16px; margin-left:auto; flex-wrap:wrap;">
        <div style="text-align:center;"><div style="color:#64748b; font-size:0.65rem;">开盘</div>
            <div style="color:#e2e8f0; font-size:0.82rem; font-weight:500;">{quote["open"]:.2f}</div></div>
        <div style="text-align:center;"><div style="color:#64748b; font-size:0.65rem;">最高</div>
            <div style="color:#ef4444; font-size:0.82rem; font-weight:500;">{quote["high"]:.2f}</div></div>
        <div style="text-align:center;"><div style="color:#64748b; font-size:0.65rem;">最低</div>
            <div style="color:#10b981; font-size:0.82rem; font-weight:500;">{quote["low"]:.2f}</div></div>
        <div style="text-align:center;"><div style="color:#64748b; font-size:0.65rem;">昨收</div>
            <div style="color:#94a3b8; font-size:0.82rem; font-weight:500;">{quote["prev_close"]:.2f}</div></div>
        <div style="text-align:center;"><div style="color:#64748b; font-size:0.65rem;">成交量</div>
            <div style="color:#e2e8f0; font-size:0.82rem; font-weight:500;">{vol_wan:.1f}万手</div></div>
        <div style="text-align:center;"><div style="color:#64748b; font-size:0.65rem;">成交额</div>
            <div style="color:#e2e8f0; font-size:0.82rem; font-weight:500;">{amt_yi:.2f}亿</div></div>
        <div style="text-align:center;"><div style="color:#64748b; font-size:0.65rem;">振幅</div>
            <div style="color:#e2e8f0; font-size:0.82rem; font-weight:500;">{quote["amplitude"]:.2f}%</div></div>
    </div>
</div>''', unsafe_allow_html=True)
    except Exception:
        pass


def _create_indicator_chart(data, name, theme="dark"):
    """创建技术指标副图"""
    template = "plotly_dark" if theme == "dark" else "plotly_white"
    fig = go.Figure()

    if name == 'MACD':
        fig.add_trace(go.Bar(
            x=data['日期'], y=data['MACD_Hist'], name='Histogram',
            marker_color=['#ef4444' if v < 0 else '#10b981' for v in data['MACD_Hist']]
        ))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['MACD'], name='MACD', line=dict(color='#3b82f6')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['MACD_Signal'], name='Signal', line=dict(color='#f59e0b')))
    elif name == 'KDJ':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_K'], name='K', line=dict(color='#3b82f6')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_D'], name='D', line=dict(color='#f59e0b')))
        fig.add_trace(go.Scatter(x=data['日期'], y=data['KDJ_J'], name='J', line=dict(color='#ec4899')))
        fig.add_hline(y=80, line_dash="dash", line_color="red")
        fig.add_hline(y=20, line_dash="dash", line_color="green")
    elif name == 'RSI':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['RSI'], name='RSI', line=dict(color='#3b82f6', fill='tozeroy')))
        fig.add_hline(y=70, line_dash="dash", line_color="red", annotation_text="超买")
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="超卖")
    elif name == 'CCI':
        fig.add_trace(go.Scatter(x=data['日期'], y=data['CCI'], name='CCI', line=dict(color='#8b5cf6')))
        fig.add_hline(y=100, line_dash="dash", line_color="red")
        fig.add_hline(y=-100, line_dash="dash", line_color="green")

    fig.update_layout(
        template=template, height=200,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


def _render_tech_observation(kline, q_metrics, stock_name, stock_code):
    """渲染深度技术分析面板：K线形态 + 技术指标 + 买点评估"""
    import pandas as pd
    import re

    if kline is None or kline.empty or len(kline) < 3:
        return

    def _b(text):
        """markdown bold → HTML strong"""
        return re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#f1f5f9">\1</strong>', text)

    def _item(text):
        return f'<div style="padding: 4px 0; border-bottom: 1px solid rgba(255,255,255,0.03);">• {_b(text)}</div>'

    latest = kline.iloc[-1]
    prev = kline.iloc[-2]

    close_p = float(latest.get('收盘', 0))
    open_p = float(latest.get('开盘', 0))
    high_p = float(latest.get('最高', 0))
    low_p = float(latest.get('最低', 0))
    volume = float(latest.get('成交量', 0))
    prev_close = float(prev.get('收盘', 0))
    prev_volume = float(prev.get('成交量', 1))

    # =============================================
    # 1. K线形态分析 (多日趋势)
    # =============================================
    kline_analysis = []

    # 近N日高低点分析
    n_days = min(len(kline), 10)
    recent = kline.tail(n_days)
    recent_high = float(recent['最高'].max())
    recent_low = float(recent['最低'].min())
    high_date = recent.loc[recent['最高'].idxmax()].get('日期', '')
    low_date = recent.loc[recent['最低'].idxmin()].get('日期', '')

    day_change = (close_p - prev_close) / prev_close * 100 if prev_close > 0 else 0

    # 从高点回落 or 从低点反弹
    if recent_high > 0 and close_p < recent_high:
        drop_from_high = (recent_high - close_p) / recent_high * 100
        if drop_from_high > 3:
            h_str = str(high_date)[:10] if high_date else ''
            l_str = str(low_date)[:10] if low_date else ''
            kline_analysis.append(
                f"从{h_str}高点 **¥{recent_high:.2f}** 跌至 ¥{recent_low:.2f}，"
                f"形成缩量调整")

    # 今日走势关键判断
    if day_change > 3:
        kline_analysis.append(f"今日出现 **大幅反弹（+{day_change:.2f}%）**，疑似主力资金介入")
    elif day_change > 1:
        kline_analysis.append(f"今日温和上涨 **+{day_change:.2f}%**，走势偏强")
    elif day_change < -3:
        kline_analysis.append(f"今日 **大幅下挫（{day_change:.2f}%）**，需警惕破位风险")
    elif day_change < -1:
        kline_analysis.append(f"今日回调 **{day_change:.2f}%**，短线承压")
    else:
        kline_analysis.append(f"今日窄幅震荡（{day_change:+.2f}%），多空分歧不大")

    # 量能分析
    if prev_volume > 0:
        vol_ratio = volume / prev_volume
        if vol_ratio > 2.0:
            kline_analysis.append(f"量能 **显著放大**（前日 {vol_ratio:.1f} 倍），资金加速流入 🔥")
        elif vol_ratio > 1.3 and day_change > 0:
            kline_analysis.append(f"**量价齐升**（量比 {vol_ratio:.1f}），上涨动力充足")
        elif vol_ratio > 1.3 and day_change < 0:
            kline_analysis.append(f"放量下跌（量比 {vol_ratio:.1f}），存在 **资金出逃** 迹象")
        elif vol_ratio < 0.6:
            kline_analysis.append("成交量 **大幅萎缩**，市场观望情绪浓厚")
        else:
            kline_analysis.append("量能配合度需进一步确认")

    # 连涨/连跌判断
    streak = 0
    for i in range(len(kline) - 1, max(len(kline) - 6, 0), -1):
        c = float(kline.iloc[i].get('收盘', 0))
        p = float(kline.iloc[i-1].get('收盘', 0)) if i > 0 else c
        if c > p:
            if streak >= 0:
                streak += 1
            else:
                break
        elif c < p:
            if streak <= 0:
                streak -= 1
            else:
                break
        else:
            break

    if streak >= 3:
        kline_analysis.append(f"已 **连涨 {streak} 日** 📈，短线注意追高风险")
    elif streak <= -3:
        kline_analysis.append(f"已 **连跌 {abs(streak)} 日** 📉，超跌反弹概率增大")

    # K线形态判断
    if close_p > 0 and open_p > 0:
        body = abs(close_p - open_p)
        upper_shadow = high_p - max(close_p, open_p)
        lower_shadow = min(close_p, open_p) - low_p
        if lower_shadow > body * 2 and upper_shadow < body * 0.5:
            kline_analysis.append("出现 **长下影线**，下方有较强支撑买盘")
        elif upper_shadow > body * 2 and lower_shadow < body * 0.5:
            kline_analysis.append("出现 **长上影线**，上方抛压较重")
        elif body < (high_p - low_p) * 0.1 and high_p - low_p > 0:
            kline_analysis.append("出现 **十字星** 形态，可能为变盘信号")

    # =============================================
    # 2. 技术指标研判
    # =============================================
    indicators = []
    rsi = q_metrics.get('rsi', 50)
    kdj_k = q_metrics.get('kdj_k', 50)
    kdj_d = q_metrics.get('kdj_d', 50)
    bb_percent = q_metrics.get('bb_percent', 50)
    dmi_adx = q_metrics.get('dmi_adx', 25)
    ma5 = latest.get('MA5', None)
    ma20 = latest.get('MA20', None)

    if rsi > 70:
        indicators.append(f"RSI **超买**（{rsi:.1f}），获利了结压力大")
    elif rsi < 30:
        indicators.append(f"RSI **超卖**（{rsi:.1f}），反弹概率增大")
    elif 45 < rsi < 55:
        indicators.append(f"RSI 中性（{rsi:.1f}），方向不明确")
    else:
        indicators.append(f"RSI {rsi:.1f}，{'偏强' if rsi > 55 else '偏弱'}")

    if kdj_k > kdj_d and kdj_k < 40:
        indicators.append("KDJ **低位金叉** 🟢，反弹动能积聚")
    elif kdj_k < kdj_d and kdj_k > 60:
        indicators.append("KDJ **高位死叉** 🔴，回调风险加大")
    elif kdj_k > 80:
        indicators.append("KDJ 进入超买区，警惕回落")

    if bb_percent > 85:
        indicators.append("触及 **布林上轨**，超涨风险高")
    elif bb_percent < 15:
        indicators.append("触及 **布林下轨**，超跌信号")

    if dmi_adx > 40:
        indicators.append(f"ADX {dmi_adx:.0f} → **强趋势**，顺势操作")
    elif dmi_adx < 20:
        indicators.append(f"ADX {dmi_adx:.0f} → **震荡行情**，区间操作")

    if pd.notna(ma5) and pd.notna(ma20):
        if close_p > float(ma5) > float(ma20):
            indicators.append("均线 **多头排列** 📈 (价格>MA5>MA20)")
        elif close_p < float(ma5) < float(ma20):
            indicators.append("均线 **空头排列** 📉 (价格<MA5<MA20)")

    # =============================================
    # 3. 买点评估（综合研判）
    # =============================================
    score = 0  # -10 ~ +10
    buy_reasons = []
    sell_reasons = []

    # RSI 信号
    if rsi < 30:
        score += 3
        buy_reasons.append("RSI 超卖区，反弹概率较高")
    elif rsi > 70:
        score -= 3
        sell_reasons.append("RSI 超买区，注意获利了结")

    # KDJ 信号
    if kdj_k > kdj_d and kdj_k < 40:
        score += 2
        buy_reasons.append("KDJ 低位金叉确认")
    elif kdj_k < kdj_d and kdj_k > 60:
        score -= 2
        sell_reasons.append("KDJ 高位死叉警告")

    # 量价配合
    if prev_volume > 0:
        vol_ratio = volume / prev_volume
        if vol_ratio > 1.3 and day_change > 0:
            score += 2
            buy_reasons.append("量价齐升，动力充足")
        elif vol_ratio > 1.3 and day_change < -2:
            score -= 2
            sell_reasons.append("放量下跌，资金出逃")

    # 布林位置
    if bb_percent < 15:
        score += 1
        buy_reasons.append("触及布林下轨，超跌反弹概率大")
    elif bb_percent > 85:
        score -= 1
        sell_reasons.append("触及布林上轨，追高风险高")

    # 均线
    if pd.notna(ma5) and pd.notna(ma20):
        if close_p > float(ma5) > float(ma20):
            score += 1
        elif close_p < float(ma5) < float(ma20):
            score -= 1

    # K线形态
    if close_p > 0 and open_p > 0:
        lower_shadow = min(close_p, open_p) - low_p
        body = abs(close_p - open_p)
        if lower_shadow > body * 2:
            score += 1
            buy_reasons.append("长下影线，下方有支撑")

    # 趋势
    if day_change > 3:
        score += 1
        buy_reasons.append(f"今日放量拉升，可能形成\"尾盘抢筹\"格局")
    elif day_change < -3:
        score -= 1
        sell_reasons.append("大幅下跌，短期止损观望")

    # 综合评级
    if score >= 3:
        signal_icon = "⚡"
        signal_text = "重点关注"
        signal_color = "#f59e0b"
        action_items = buy_reasons
        action_intro = "看多信号"
    elif score <= -3:
        signal_icon = "⛔"
        signal_text = "风险警示"
        signal_color = "#ef4444"
        action_items = sell_reasons
        action_intro = "风险信号"
    else:
        signal_icon = "⏳"
        signal_text = "观望等待"
        signal_color = "#94a3b8"
        action_items = buy_reasons + sell_reasons if buy_reasons or sell_reasons else ["多空力量均衡，等待方向明确"]
        action_intro = "中性信号"

    # 关键价位
    price_levels = []
    if pd.notna(ma5):
        price_levels.append(f"MA5 ¥{float(ma5):.2f}")
    if pd.notna(ma20):
        price_levels.append(f"MA20 ¥{float(ma20):.2f}")

    # 整数关口
    if close_p > 10:
        round_above = (int(close_p / 10) + 1) * 10
        round_below = int(close_p / 10) * 10
        if round_above - close_p < close_p * 0.05:
            price_levels.append(f"关注 **¥{round_above}** 整数关口突破")
        if close_p - round_below < close_p * 0.03:
            price_levels.append(f"关注 **¥{round_below}** 整数支撑")

    # =============================================
    # 渲染
    # =============================================
    kline_html = "".join([_item(t) for t in kline_analysis])
    indicator_html = "".join([_item(t) for t in indicators])
    action_html = "".join([_item(t) for t in action_items])
    price_html = "".join([_item(t) for t in price_levels]) if price_levels else ""

    # 构建关键价位 HTML（单独处理，避免 f-string 嵌套引号问题）
    price_section = ""
    if price_html:
        price_section = (
            '<div style="margin-top: 12px; padding-top: 10px; '
            'border-top: 1px solid rgba(255,255,255,0.06);">'
            '<div style="font-size: 0.85rem; font-weight: 600; '
            'color: #94a3b8; margin-bottom: 6px;">关键价位：</div>'
            '<div style="color: #cbd5e1; font-size: 0.82rem; '
            f'line-height: 1.7;">{price_html}</div></div>'
        )

    # 根据评分确定边框颜色
    if score <= -3:
        border_rgb = "239,68,68"
    elif score >= 3:
        border_rgb = "245,158,11"
    else:
        border_rgb = "148,163,184"

    col1, col2 = st.columns(2)

    # 左列：K线形态 + 技术指标
    with col1:
        left_html = (
            '<div style="background: linear-gradient(145deg, rgba(30,41,59,0.6), rgba(15,23,42,0.7));'
            ' border: 1px solid rgba(56,189,248,0.15); border-radius: 14px; padding: 20px;">'
            '<div style="font-size: 0.95rem; font-weight: 700; color: #f1f5f9;'
            ' margin-bottom: 12px;">K线形态分析：</div>'
            f'<div style="color: #cbd5e1; font-size: 0.82rem; line-height: 1.7;">{kline_html}</div>'
            '<div style="font-size: 0.95rem; font-weight: 700; color: #f1f5f9;'
            ' margin-top: 16px; margin-bottom: 10px; padding-top: 12px;'
            ' border-top: 1px solid rgba(255,255,255,0.06);">技术指标研判：</div>'
            f'<div style="color: #cbd5e1; font-size: 0.82rem; line-height: 1.7;">{indicator_html}</div>'
            '</div>'
        )
        st.markdown(left_html, unsafe_allow_html=True)

    # 右列：买点评估
    with col2:
        right_html = (
            f'<div style="background: linear-gradient(145deg, rgba(30,41,59,0.6), rgba(15,23,42,0.7));'
            f' border: 1px solid rgba({border_rgb},0.25);'
            f' border-left: 4px solid {signal_color}; border-radius: 14px; padding: 20px;">'
            f'<div style="font-size: 0.95rem; font-weight: 700; color: #f1f5f9; margin-bottom: 6px;">'
            f'买点评估：<span style="color: {signal_color}; margin-left: 8px;'
            f' font-size: 1rem;">{signal_icon} {signal_text}</span></div>'
            f'<div style="font-size: 0.75rem; color: #64748b; margin-bottom: 12px;">'
            f'综合得分 {score:+d} | {action_intro}</div>'
            f'<div style="color: #cbd5e1; font-size: 0.82rem; line-height: 1.7;">{action_html}</div>'
            f'{price_section}'
            '<div style="color: #64748b; font-size: 0.68rem; margin-top: 14px;'
            ' padding-top: 8px; border-top: 1px solid rgba(255,255,255,0.05);">'
            '⚠️ 算法自动生成，仅供参考，不构成投资建议</div>'
            '</div>'
        )
        st.markdown(right_html, unsafe_allow_html=True)



def render_dna_analyzer(L, my_stocks, name_map, default_target=None):
    """
    渲染 DNA Analyzer (可嵌入任意页面)
    使用 Tabs 组织信息层级：行情走势 | 技术分析 | AI 研判
    """
    st.divider()

    # ---- 标的选择 + 刷新 (始终可见，不放在 Tab 里) ----
    target = default_target if default_target else st.session_state.get('selected_stock', '601318')
    if target not in my_stocks:
        my_stocks_dropdown = [target] + my_stocks
        if target not in name_map:
            new_names = get_stock_names_batch([target])
            name_map.update(new_names)
    else:
        my_stocks_dropdown = my_stocks

    hdr_col, sel_col, refresh_col = st.columns([2, 3, 1])
    with hdr_col:
        st.markdown(f"### {L.get('dna_analysis', '🧬 深度决策中心')}")
    with sel_col:
        sel_stock = st.selectbox(
            "标的", my_stocks_dropdown,
            index=my_stocks_dropdown.index(target) if target in my_stocks_dropdown else 0,
            format_func=lambda x: f"{x} {name_map.get(x, '')}",
            label_visibility="collapsed"
        )
        st.session_state['selected_stock'] = sel_stock
    with refresh_col:
        if st.button("🔄", key=f"refresh_{id(render_dna_analyzer)}", use_container_width=True, help="刷新当前标的"):
            # 仅清除当前股票相关缓存, 不清全局
            try:
                from core.cache import RedisCache
                _rc = RedisCache()
                if _rc.ping():
                    for pattern in [f"kline:{sel_stock}*", f"strat:*{sel_stock}*"]:
                        _rc.delete(pattern)
            except Exception:
                pass
            st.cache_data.clear()
            st.toast(f"📊 {sel_stock} 数据已刷新", icon="✨")
            st.rerun()

    # ---- 数据获取 (所有 Tab 共享) ----
    if 'selected_period' not in st.session_state:
        st.session_state['selected_period'] = 'daily'
    if 'selected_indicators' not in st.session_state:
        st.session_state['selected_indicators'] = ['MA']

    selected_period = st.session_state.get('selected_period', 'daily')
    full_symbol = "sh" + sel_stock if sel_stock.startswith('6') else "sz" + sel_stock
    kline = fetch_kline(full_symbol, period=selected_period, datalen=100)

    if not kline.empty and calculate_all_indicators:
        kline = calculate_all_indicators(kline)

    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}

    # ========== 六大 Tab ==========
    tab_chart, tab_tech, tab_fund, tab_dragon, tab_ai, tab_profile = st.tabs(
        ["📊 走势", "🔬 技术", "💰 资金", "🐉 龙虎", "🤖 AI", "🏢 简介"])

    # -------- Tab 1: 行情走势 --------
    with tab_chart:
        # 时间周期选择器 (紧凑行内)
        period_cols = st.columns(8)
        periods = ['1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly']
        period_labels = ['1分', '5分', '15分', '30分', '60分', '日线', '周线', '月线']

        for i, (period, label) in enumerate(zip(periods, period_labels)):
            with period_cols[i]:
                if st.button(label, key=f"period_{period}_{id(render_dna_analyzer)}",
                            type="primary" if st.session_state['selected_period'] == period else "secondary",
                            use_container_width=True):
                    st.session_state['selected_period'] = period
                    st.rerun()

        # 均线叠加选择 (紧凑)
        ind_cols = st.columns(6)
        available_indicators = {'MA': '均线', 'BB': '布林带', 'MACD': 'MACD', 'KDJ': 'KDJ', 'RSI': 'RSI', 'CCI': 'CCI'}
        for i, (key, label) in enumerate(available_indicators.items()):
            with ind_cols[i]:
                is_selected = key in st.session_state['selected_indicators']
                if st.button(label, key=f"ind_{key}_{id(render_dna_analyzer)}",
                            type="primary" if is_selected else "secondary",
                            use_container_width=True):
                    if is_selected:
                        st.session_state['selected_indicators'].remove(key)
                    else:
                        st.session_state['selected_indicators'].append(key)
                    st.rerun()

        # ---- 当日基本信息面板 ----
        _render_daily_info(full_symbol, name_map.get(sel_stock, sel_stock))

        # K线图
        if not kline.empty and render_tv_chart:
            indicators_to_show = []
            selected_indicators = st.session_state.get('selected_indicators', ['MA'])

            if 'MA' in selected_indicators:
                indicators_to_show.extend(['MA5', 'MA20', 'MA60'])
            if 'BB' in selected_indicators and 'BB_Upper' in kline.columns:
                indicators_to_show.extend(['BB_Upper', 'BB_Middle', 'BB_Lower'])

            theme_str = st.session_state.get('theme', 'dark')
            render_tv_chart(kline, height=480, theme=theme_str, indicators=indicators_to_show)

            # 副图指标 (折叠)
            sub_indicators = []
            if 'MACD' in selected_indicators and 'MACD' in kline.columns:
                sub_indicators.append(('MACD', kline[['日期', 'MACD', 'MACD_Signal', 'MACD_Hist']]))
            if 'KDJ' in selected_indicators and 'KDJ_K' in kline.columns:
                sub_indicators.append(('KDJ', kline[['日期', 'KDJ_K', 'KDJ_D', 'KDJ_J']]))
            if 'RSI' in selected_indicators and 'RSI' in kline.columns:
                sub_indicators.append(('RSI', kline[['日期', 'RSI']]))
            if 'CCI' in selected_indicators and 'CCI' in kline.columns:
                sub_indicators.append(('CCI', kline[['日期', 'CCI']]))

            for name, data in sub_indicators:
                with st.expander(f"📈 {name} 指标", expanded=False):
                    sub_fig = _create_indicator_chart(data, name, theme_str)
                    st.plotly_chart(sub_fig, use_container_width=True, height=250)

        # 技术观察 + 策略建议 (并排)
        _render_tech_observation(kline, q_metrics, name_map.get(sel_stock, sel_stock), sel_stock)

    # -------- Tab 2: 技术分析 --------
    with tab_tech:
        # 核心指标卡片 (3列更宽敞)
        r1c1, r1c2, r1c3 = st.columns(3)
        fin_score = f_data.get('score', 50) if f_data else 50
        fin_source = f_data.get('source', '') if f_data else ''
        r1c1.metric(L.get('fin_health', '财务健康分'), f"{fin_score}%", delta=fin_source if fin_source else None, delta_color="off")
        r1c2.metric("RSI(14)", f"{q_metrics.get('rsi', 0):.1f}")
        r1c3.metric(L.get('ann_vol', '年化波动率'), f"{q_metrics.get('volatility_ann', 0):.1f}%")

        r2c1, r2c2, r2c3 = st.columns(3)
        bb_width = q_metrics.get('bb_width', 0)
        bb_pos = "中轨附近"
        if q_metrics.get('bb_percent', 50) > 80:
            bb_pos = "上轨附近⚠️"
        elif q_metrics.get('bb_percent', 50) < 20:
            bb_pos = "下轨附近💡"
        r2c1.metric("布林带", f"{bb_width:.1f}%", delta=bb_pos, delta_color="off")

        kdj_k = q_metrics.get('kdj_k', 50)
        kdj_d = q_metrics.get('kdj_d', 50)
        kdj_signal = "金叉" if kdj_k > kdj_d and kdj_k < 50 else "死叉" if kdj_k < kdj_d else "整理"
        r2c2.metric(f"KDJ(K:{kdj_k:.1f})", f"D:{kdj_d:.1f}", delta=kdj_signal,
                  delta_color="normal" if kdj_signal == "金叉" else "inverse")

        dmi_adx = q_metrics.get('dmi_adx', 0)
        adx_strength = "强趋势" if dmi_adx > 40 else "弱趋势" if dmi_adx < 20 else "震荡"
        r2c3.metric(f"ADX({dmi_adx:.1f})", adx_strength)

        if f_data and f_data.get('analysis'):
            st.caption(f"📊 {f_data['analysis']}")

        # 行情快照
        st.divider()
        if not kline.empty:
            latest = kline.iloc[-1]
            snap_cols = st.columns(5)
            snap_cols[0].metric("开盘", f"¥{latest.get('开盘', 0):.2f}")
            snap_cols[1].metric("最高", f"¥{latest.get('最高', 0):.2f}")
            snap_cols[2].metric("最低", f"¥{latest.get('最低', 0):.2f}")
            snap_cols[3].metric("收盘", f"¥{latest.get('收盘', 0):.2f}")
            vol = latest.get('成交量', 0)
            vol_str = f"{vol/10000:.0f}万手" if vol > 10000 else f"{vol:.0f}手"
            snap_cols[4].metric("成交量", vol_str)

    # -------- Tab 3: AI 研判 --------
    with tab_ai:
        st.caption(f"数据时间: {datetime.datetime.now().strftime('%H:%M:%S')}")

        cached, is_cached = load_cached_report(sel_stock)

        if is_cached:
            st.success("📄 已有今日 AI 报告", icon="✅")
        else:
            st.info("🤖 点击下方按钮生成 AI 深度分析报告", icon="💡")

        if st.button(L.get('invoke_ai', '启动多模态 AI 研判'), key=f"invoke_ai_{id(render_dna_analyzer)}", type="primary", use_container_width=True):
            with st.spinner("🧠 AI 正在分析市场数据..."):
                rep = generate_ai_report(sel_stock, name_map.get(sel_stock, ''),
                                        fetch_research_reports(sel_stock),
                                        fetch_trading_signals(full_symbol))

                st.success("✅ 分析完成！")
                st.markdown(f"<div class='ai-box'>{rep}</div>", unsafe_allow_html=True)

                os.makedirs(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}", exist_ok=True)
                with open(f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{sel_stock}.md", "w") as f:
                    f.write(rep)

                st.toast("报告已保存", icon="📁")
                st.balloons()
        elif is_cached:
            st.markdown(f"<div class='ai-box'>{cached}</div>", unsafe_allow_html=True)

    # -------- Tab 3: 资金面 --------
    with tab_fund:
        st.caption(f"💰 {name_map.get(sel_stock, sel_stock)} 资金面分析 | 数据来源: Tushare Pro")
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            if not ts.available:
                st.warning("Tushare 未连接，资金面数据不可用")
            else:
                fund_c1, fund_c2 = st.columns(2)

                # 个股资金流向
                with fund_c1:
                    st.markdown("##### 📊 资金流向 (近 20 日)")
                    mf = ts.get_moneyflow_single(sel_stock, days=20)
                    if mf is not None and not mf.empty:
                        fig_mf = go.Figure()
                        dates = mf['trade_date'].astype(str)
                        # 净流入 = 买入 - 卖出
                        for label, buy_col, sell_col, color in [
                            ('超大单', 'buy_elg_vol', 'sell_elg_vol', '#ef4444'),
                            ('大单', 'buy_lg_vol', 'sell_lg_vol', '#f97316'),
                            ('中单', 'buy_md_vol', 'sell_md_vol', '#3b82f6'),
                            ('小单', 'buy_sm_vol', 'sell_sm_vol', '#10b981'),
                        ]:
                            if buy_col in mf.columns and sell_col in mf.columns:
                                net = mf[buy_col].astype(float) - mf[sell_col].astype(float)
                                fig_mf.add_trace(go.Bar(
                                    x=dates, y=net / 10000,
                                    name=label, marker_color=color, opacity=0.8
                                ))
                        fig_mf.update_layout(
                            barmode='group', template='plotly_dark',
                            height=320, margin=dict(l=10, r=10, t=30, b=30),
                            yaxis_title='净流入(万手)', legend=dict(orientation='h', y=1.02)
                        )
                        st.plotly_chart(fig_mf, use_container_width=True, key=f"mf_{sel_stock}")

                        # 总净流入指标
                        if 'net_mf_vol' in mf.columns:
                            latest_net = float(mf.iloc[-1]['net_mf_vol'] or 0)
                            trend = sum(mf['net_mf_vol'].astype(float).tail(5)) / 5
                            m1, m2 = st.columns(2)
                            m1.metric("最新净流入", f"{latest_net/10000:.1f}万手")
                            m2.metric("5日均值", f"{trend/10000:.1f}万手",
                                     delta="净流入" if trend > 0 else "净流出",
                                     delta_color="normal" if trend > 0 else "inverse")
                    else:
                        st.info("暂无资金流向数据")

                # 融资融券
                with fund_c2:
                    st.markdown("##### 📈 融资融券余额 (近 30 日)")
                    mg = ts.get_margin(sel_stock, days=30)
                    if mg is not None and not mg.empty:
                        fig_mg = go.Figure()
                        dates_mg = mg['trade_date'].astype(str)
                        if 'rzye' in mg.columns:
                            rzye = mg['rzye'].astype(float) / 1e8
                            fig_mg.add_trace(go.Scatter(
                                x=dates_mg, y=rzye, name='融资余额(亿)',
                                line=dict(color='#ef4444', width=2), fill='tozeroy',
                                fillcolor='rgba(239,68,68,0.1)'
                            ))
                        if 'rqye' in mg.columns:
                            rqye = mg['rqye'].astype(float) / 1e8
                            fig_mg.add_trace(go.Scatter(
                                x=dates_mg, y=rqye, name='融券余额(亿)',
                                line=dict(color='#3b82f6', width=2), yaxis='y2'
                            ))
                        fig_mg.update_layout(
                            template='plotly_dark', height=320,
                            margin=dict(l=10, r=50, t=30, b=30),
                            yaxis=dict(title='融资余额(亿)'),
                            yaxis2=dict(title='融券余额(亿)', overlaying='y', side='right'),
                            legend=dict(orientation='h', y=1.02)
                        )
                        st.plotly_chart(fig_mg, use_container_width=True, key=f"mg_{sel_stock}")

                        # 融资指标
                        if 'rzye' in mg.columns:
                            latest_rz = float(mg.iloc[-1]['rzye'] or 0) / 1e8
                            prev_rz = float(mg.iloc[-2]['rzye'] or 0) / 1e8 if len(mg) > 1 else latest_rz
                            change_rz = latest_rz - prev_rz
                            m1, m2 = st.columns(2)
                            m1.metric("融资余额", f"{latest_rz:.2f}亿",
                                     delta=f"{change_rz:+.2f}亿",
                                     delta_color="normal" if change_rz > 0 else "inverse")
                            if 'rzmre' in mg.columns:
                                rzmre = float(mg.iloc[-1].get('rzmre', 0) or 0) / 1e8
                                m2.metric("融资买入", f"{rzmre:.2f}亿")
                    else:
                        st.info("暂无融资融券数据 (可能该股不支持两融)")

                # 股东人数变化
                st.divider()
                st.markdown("##### 👥 股东人数变化")
                hn = ts.get_holder_number(sel_stock)
                if hn is not None and not hn.empty:
                    fig_hn = go.Figure()
                    hn_sorted = hn.sort_values('end_date')
                    if 'holder_num' in hn_sorted.columns:
                        fig_hn.add_trace(go.Scatter(
                            x=hn_sorted['end_date'].astype(str),
                            y=hn_sorted['holder_num'].astype(float) / 10000,
                            name='股东人数(万)', mode='lines+markers',
                            line=dict(color='#8b5cf6', width=2),
                            marker=dict(size=8)
                        ))
                        fig_hn.update_layout(
                            template='plotly_dark', height=250,
                            margin=dict(l=10, r=10, t=30, b=30),
                            yaxis_title='股东人数(万)'
                        )
                        st.plotly_chart(fig_hn, use_container_width=True, key=f"hn_{sel_stock}")
                        latest_hn = float(hn_sorted.iloc[-1].get('holder_num', 0) or 0)
                        prev_hn = float(hn_sorted.iloc[-2].get('holder_num', 0) or 0) if len(hn_sorted) > 1 else latest_hn
                        change_hn = latest_hn - prev_hn
                        st.caption(f"最新股东人数: {latest_hn/10000:.2f}万 | 变化: {change_hn/10000:+.2f}万 {'(筹码集中)' if change_hn < 0 else '(筹码分散)'}")
                else:
                    st.info("暂无股东人数数据")
        except Exception as e:
            st.error(f"资金面数据加载失败: {e}")

    # -------- Tab 4: 龙虎榜 --------
    with tab_dragon:
        st.caption(f"🐉 {name_map.get(sel_stock, sel_stock)} 龙虎榜 & 大宗交易 | 数据来源: Tushare Pro")
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            if not ts.available:
                st.warning("Tushare 未连接，龙虎榜数据不可用")
            else:
                dragon_c1, dragon_c2 = st.columns([3, 2])

                # 龙虎榜记录
                with dragon_c1:
                    st.markdown("##### 📋 龙虎榜上榜记录")
                    top = ts.get_top_list(symbol=sel_stock)
                    if top is not None and not top.empty:
                        display_cols = []
                        col_rename = {}
                        for orig, disp in [
                            ('trade_date', '日期'), ('reason', '上榜原因'),
                            ('close', '收盘'), ('pct_change', '涨跌幅'),
                            ('turnover_rate', '换手率'),
                            ('buy', '买入额(万)'), ('sell', '卖出额(万)'),
                            ('net_buy', '净买入(万)')  
                        ]:
                            if orig in top.columns:
                                display_cols.append(orig)
                                col_rename[orig] = disp

                        show_df = top[display_cols].rename(columns=col_rename) if display_cols else top
                        # 格式化金额为万
                        for c in ['买入额(万)', '卖出额(万)', '净买入(万)']:
                            if c in show_df.columns:
                                show_df[c] = show_df[c].apply(
                                    lambda x: f"{float(x or 0)/10000:.0f}" if x else '0')
                        st.dataframe(show_df.head(10), use_container_width=True, hide_index=True)
                    else:
                        st.info("该股近期未上龙虎榜")

                    # 营业部明细
                    st.markdown("##### 🏢 龙虎榜营业部")
                    inst = ts.get_top_inst(symbol=sel_stock)
                    if inst is not None and not inst.empty:
                        inst_cols = []
                        inst_rename = {}
                        for orig, disp in [
                            ('trade_date', '日期'), ('exalter', '营业部'),
                            ('buy', '买入(万)'), ('sell', '卖出(万)'),
                            ('net_buy', '净买入(万)'), ('side', '方向')
                        ]:
                            if orig in inst.columns:
                                inst_cols.append(orig)
                                inst_rename[orig] = disp
                        show_inst = inst[inst_cols].rename(columns=inst_rename) if inst_cols else inst
                        for c in ['买入(万)', '卖出(万)', '净买入(万)']:
                            if c in show_inst.columns:
                                show_inst[c] = show_inst[c].apply(
                                    lambda x: f"{float(x or 0)/10000:.0f}" if x else '0')
                        st.dataframe(show_inst.head(15), use_container_width=True, hide_index=True)
                    else:
                        st.info("暂无营业部数据")

                # 大宗交易
                with dragon_c2:
                    st.markdown("##### 📦 大宗交易记录")
                    bt = ts.get_block_trade(symbol=sel_stock, days=60)
                    if bt is not None and not bt.empty:
                        bt_cols = []
                        bt_rename = {}
                        for orig, disp in [
                            ('trade_date', '日期'), ('price', '成交价'),
                            ('vol', '成交量(万股)'), ('amount', '成交额(万)'),
                            ('buyer', '买方'), ('seller', '卖方')
                        ]:
                            if orig in bt.columns:
                                bt_cols.append(orig)
                                bt_rename[orig] = disp
                        show_bt = bt[bt_cols].rename(columns=bt_rename) if bt_cols else bt
                        if '成交量(万股)' in show_bt.columns:
                            show_bt['成交量(万股)'] = show_bt['成交量(万股)'].apply(
                                lambda x: f"{float(x or 0)/10000:.1f}")
                        if '成交额(万)' in show_bt.columns:
                            show_bt['成交额(万)'] = show_bt['成交额(万)'].apply(
                                lambda x: f"{float(x or 0)/10000:.0f}")
                        st.dataframe(show_bt.head(10), use_container_width=True, hide_index=True)

                        # 大宗交易趋势
                        if 'amount' in bt.columns and len(bt) > 2:
                            fig_bt = go.Figure()
                            bt_sorted = bt.sort_values('trade_date')
                            fig_bt.add_trace(go.Bar(
                                x=bt_sorted['trade_date'].astype(str),
                                y=bt_sorted['amount'].astype(float) / 1e4,
                                name='成交额(万)', marker_color='#8b5cf6', opacity=0.8
                            ))
                            fig_bt.update_layout(
                                template='plotly_dark', height=250,
                                margin=dict(l=10, r=10, t=30, b=30),
                                yaxis_title='成交额(万)'
                            )
                            st.plotly_chart(fig_bt, use_container_width=True, key=f"bt_{sel_stock}")
                    else:
                        st.info("该股近期无大宗交易")

                # 股东增减持
                st.divider()
                st.markdown("##### 📢 股东增减持")
                ht = ts.get_holder_trade(sel_stock)
                if ht is not None and not ht.empty:
                    ht_cols = []
                    ht_rename = {}
                    for orig, disp in [
                        ('ann_date', '公告日'), ('holder_name', '股东名称'),
                        ('holder_type', '类型'), ('in_de', '增/减持'),
                        ('change_vol', '变动股数(万)'), ('change_ratio', '占比%'),
                        ('after_share', '变动后持股(万)'), ('after_ratio', '变动后占比%')
                    ]:
                        if orig in ht.columns:
                            ht_cols.append(orig)
                            ht_rename[orig] = disp
                    show_ht = ht[ht_cols].rename(columns=ht_rename) if ht_cols else ht
                    if '变动股数(万)' in show_ht.columns:
                        show_ht['变动股数(万)'] = show_ht['变动股数(万)'].apply(
                            lambda x: f"{float(x or 0)/10000:.1f}")
                    if '变动后持股(万)' in show_ht.columns:
                        show_ht['变动后持股(万)'] = show_ht['变动后持股(万)'].apply(
                            lambda x: f"{float(x or 0)/10000:.1f}")
                    st.dataframe(show_ht, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无股东增减持记录")
        except Exception as e:
            st.error(f"龙虎榜数据加载失败: {e}")

    # -------- Tab 6: 公司简介 --------
    with tab_profile:
        stock_name_display = name_map.get(sel_stock, sel_stock)
        st.caption(f"🏢 {stock_name_display} 公司简介 | 数据来源: Tushare Pro")
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            if not ts.available:
                st.warning("Tushare 未连接，公司简介不可用")
            else:
                # 公司详细信息
                company = ts.get_stock_company(sel_stock)
                # 基础信息 (行业/地区/上市日期)
                basics = ts.get_stock_basic()
                basic_info = {}
                if basics is not None and not basics.empty:
                    row = basics[basics['symbol'] == sel_stock]
                    if not row.empty:
                        basic_info = row.iloc[0].to_dict()

                if company is not None and not company.empty:
                    c = company.iloc[0]

                    # ---- 头部: 公司名 + 行业标签 ----
                    industry = basic_info.get('industry', '')
                    area = basic_info.get('area', c.get('province', ''))
                    list_date = basic_info.get('list_date', '')
                    if list_date and len(str(list_date)) == 8:
                        list_date = f"{str(list_date)[:4]}-{str(list_date)[4:6]}-{str(list_date)[6:]}"

                    industry_badge = f'<span class="badge badge-info" style="margin-left:8px;">{industry}</span>' if industry else ''
                    area_badge = f'<span class="badge badge-success" style="margin-left:4px;">{area}</span>' if area else ''

                    st.markdown(f'''<div style="margin-bottom: 16px;">
    <span style="font-family: Outfit, sans-serif; font-size: 1.4rem; font-weight: 700;
          color: #f1f5f9;">{stock_name_display}</span>
    <span style="color: #64748b; font-size: 0.85rem; margin-left: 8px;">{sel_stock}</span>
    {industry_badge}{area_badge}
</div>''', unsafe_allow_html=True)

                    # ---- 关键信息卡片 (2列) ----
                    prof_c1, prof_c2 = st.columns([2, 3])

                    with prof_c1:
                        chairman = c.get('chairman', '—') or '—'
                        manager = c.get('manager', '—') or '—'
                        secretary = c.get('secretary', '—') or '—'
                        reg_capital = c.get('reg_capital', 0)
                        try:
                            reg_capital = float(reg_capital or 0)
                            reg_str = f"{reg_capital/10000:.2f} 亿元" if reg_capital > 10000 else f"{reg_capital:.0f} 万元"
                        except (ValueError, TypeError):
                            reg_str = str(reg_capital)
                        employees = c.get('employees', 0)
                        try:
                            employees = int(float(employees or 0))
                            emp_str = f"{employees:,} 人"
                        except (ValueError, TypeError):
                            emp_str = str(employees)
                        setup_date = c.get('setup_date', '—') or '—'
                        if setup_date and len(str(setup_date)) == 8:
                            setup_date = f"{str(setup_date)[:4]}-{str(setup_date)[4:6]}-{str(setup_date)[6:]}"
                        website = c.get('website', '') or ''
                        email = c.get('email', '') or ''

                        # 信息卡
                        items = [
                            ('👤 董事长', chairman),
                            ('👨‍💼 总经理', manager),
                            ('📝 董秘', secretary),
                            ('💰 注册资本', reg_str),
                            ('👥 员工人数', emp_str),
                            ('📅 成立日期', str(setup_date)),
                            ('📅 上市日期', str(list_date) if list_date else '—'),
                        ]

                        rows_html = ''.join(
                            f'<div style="display:flex; justify-content:space-between; padding:6px 0;'
                            f' border-bottom:1px solid rgba(255,255,255,0.04);'
                            f' font-size:0.85rem;">'
                            f'<span style="color:#94a3b8;">{label}</span>'
                            f'<span style="color:#e2e8f0; font-weight:500;">{val}</span></div>'
                            for label, val in items
                        )

                        web_html = ''
                        if website:
                            web_html = (f'<div style="margin-top:10px; font-size:0.82rem;">'
                                        f'<span style="color:#94a3b8;">🌐 </span>'
                                        f'<a href="{website}" target="_blank" '
                                        f'style="color:#38bdf8; text-decoration:none;">{website}</a></div>')
                        if email:
                            web_html += (f'<div style="font-size:0.82rem;">'
                                         f'<span style="color:#94a3b8;">📧 </span>'
                                         f'<span style="color:#cbd5e1;">{email}</span></div>')

                        st.markdown(f'''<div class="ssm-card">
    <div style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9;
         margin-bottom: 10px;">📋 基本信息</div>
    {rows_html}
    {web_html}
</div>''', unsafe_allow_html=True)

                    with prof_c2:
                        # 主营业务
                        main_biz = c.get('main_business', '') or ''
                        if main_biz:
                            st.markdown(f'''<div class="ssm-card" style="margin-bottom: 12px;">
    <div style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9;
         margin-bottom: 8px;">💼 主营业务</div>
    <div style="color: #cbd5e1; font-size: 0.85rem; line-height: 1.7;">{main_biz}</div>
</div>''', unsafe_allow_html=True)

                        # 公司简介
                        intro = c.get('introduction', '') or ''
                        if intro:
                            # 截断过长简介并提供展开
                            if len(intro) > 300:
                                with st.expander("📖 公司简介", expanded=True):
                                    st.markdown(f'''<div style="color: #cbd5e1; font-size: 0.85rem;
                                         line-height: 1.8;">{intro}</div>''',
                                               unsafe_allow_html=True)
                            else:
                                st.markdown(f'''<div class="ssm-card">
    <div style="font-size: 0.9rem; font-weight: 600; color: #f1f5f9;
         margin-bottom: 8px;">📖 公司简介</div>
    <div style="color: #cbd5e1; font-size: 0.85rem; line-height: 1.8;">{intro}</div>
</div>''', unsafe_allow_html=True)

                        # 经营范围
                        biz_scope = c.get('business_scope', '') or ''
                        if biz_scope:
                            with st.expander("📜 经营范围"):
                                st.markdown(f'''<div style="color: #94a3b8; font-size: 0.82rem;
                                     line-height: 1.7;">{biz_scope}</div>''',
                                           unsafe_allow_html=True)
                else:
                    st.info("暂无公司简介数据")
        except Exception as e:
            st.error(f"公司简介加载失败: {e}")
