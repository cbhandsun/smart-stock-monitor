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
        if st.button("🔄", key=f"refresh_{id(render_dna_analyzer)}", use_container_width=True, help="刷新数据"):
            st.cache_data.clear()
            st.toast("数据已刷新", icon="✨")
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

    # ========== 三大 Tab ==========
    tab_chart, tab_tech, tab_ai = st.tabs(["📊 行情走势", "🔬 技术分析", "🤖 AI 研判"])

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
