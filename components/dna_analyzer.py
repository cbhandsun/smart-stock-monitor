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
    """渲染技术观察 + 策略建议面板"""
    import pandas as pd

    if kline is None or kline.empty or len(kline) < 2:
        return

    latest = kline.iloc[-1]
    prev = kline.iloc[-2]

    open_p = float(latest.get('开盘', 0))
    high_p = float(latest.get('最高', 0))
    low_p = float(latest.get('最低', 0))
    close_p = float(latest.get('收盘', 0))
    volume = float(latest.get('成交量', 0))
    prev_close = float(prev.get('收盘', 0))
    prev_volume = float(prev.get('成交量', 1))

    # ---- 技术观察 ----
    observations = []

    if low_p > 0:
        amplitude = (high_p - low_p) / low_p * 100
        observations.append(f"盘中振幅 **{amplitude:.2f}%**（最高 ¥{high_p:.2f}，最低 ¥{low_p:.2f}）")

    if open_p > 0 and close_p > 0:
        oc_change = (close_p - open_p) / open_p * 100
        if oc_change > 0.3:
            observations.append(f"从开盘价上涨 **{oc_change:.2f}%**，呈现低开高走态势")
        elif oc_change < -0.3:
            observations.append(f"从开盘价回落 **{abs(oc_change):.2f}%**，呈现冲高回落态势")
        else:
            observations.append(f"收盘价与开盘价接近（变化 {oc_change:.2f}%），多空胶着")

    if prev_close > 0:
        day_change = (close_p - prev_close) / prev_close * 100
        direction = "上涨" if day_change > 0 else "下跌"
        observations.append(f"较前一交易日{direction} **{abs(day_change):.2f}%**")

    if prev_volume > 0:
        vol_ratio = volume / prev_volume
        if vol_ratio > 1.5:
            observations.append(f"成交量放大至前日 **{vol_ratio:.1f} 倍**，资金活跃度显著提升 🔥")
        elif vol_ratio < 0.7:
            observations.append(f"成交量萎缩至前日 **{vol_ratio:.1f} 倍**，市场观望情绪浓厚")
        else:
            observations.append(f"成交量与前日基本持平（比值 {vol_ratio:.2f}）")

    ma5 = latest.get('MA5', None)
    ma20 = latest.get('MA20', None)

    if pd.notna(ma5) and pd.notna(ma20):
        if close_p > float(ma5) > float(ma20):
            observations.append("价格位于 MA5 和 MA20 **上方**，短期多头排列 📈")
        elif close_p < float(ma5) < float(ma20):
            observations.append("价格位于 MA5 和 MA20 **下方**，短期空头排列 📉")
        elif float(ma5) > float(ma20) and close_p < float(ma5):
            observations.append("MA5 仍在 MA20 上方，但价格已跌破 MA5，注意短期回调风险")

    # ---- 策略建议 ----
    strategies = []
    rsi = q_metrics.get('rsi', 50)
    kdj_k = q_metrics.get('kdj_k', 50)
    kdj_d = q_metrics.get('kdj_d', 50)
    bb_percent = q_metrics.get('bb_percent', 50)
    dmi_adx = q_metrics.get('dmi_adx', 25)

    if rsi > 70:
        strategies.append("RSI 进入超买区（{:.1f}），短线获利了结压力增大，建议逢高减仓".format(rsi))
    elif rsi < 30:
        strategies.append("RSI 进入超卖区（{:.1f}），短线反弹概率增大，可关注右侧信号介入".format(rsi))
    elif 40 < rsi < 60:
        strategies.append("RSI 处于中性区间（{:.1f}），方向不明确，以观望为主".format(rsi))

    if kdj_k > kdj_d and kdj_k < 40:
        strategies.append("KDJ 低位金叉形成 🟢，短期反弹动能积聚")
    elif kdj_k < kdj_d and kdj_k > 60:
        strategies.append("KDJ 高位死叉 🔴，短期回调风险加大")

    if bb_percent > 85:
        strategies.append("价格触及布林带上轨，短期超涨风险较高，不建议追高")
    elif bb_percent < 15:
        strategies.append("价格触及布林带下轨，超跌反弹概率增大，可考虑分批试探")

    if dmi_adx > 40:
        strategies.append("ADX > 40，当前处于**强趋势行情**，建议顺势操作，不宜逆势")
    elif dmi_adx < 20:
        strategies.append("ADX < 20，当前处于**震荡行情**，建议区间操作，高抛低吸")

    if pd.notna(ma20) and pd.notna(ma5):
        support = min(float(ma5), float(ma20))
        resistance = high_p
        strategies.append(f"关注 ¥{support:.2f} 附近支撑 | ¥{resistance:.2f} 附近压力")

    # 转换 markdown bold 为 HTML（因为渲染在 HTML div 里）
    import re
    def _md_to_html(text):
        return re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:#f1f5f9">\1</strong>', text)

    obs_items = [_md_to_html(o) for o in observations] if observations else ["数据不足，暂无观察"]
    strat_items = [_md_to_html(s) for s in strategies] if strategies else ["数据不足，暂无策略"]

    obs_html = "".join([
        f'<div style="padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.03);">• {o}</div>'
        for o in obs_items
    ])
    strat_html = "".join([
        f'<div style="padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.03);">• {s}</div>'
        for s in strat_items
    ])

    # 使用两列并排显示
    col_obs, col_strat = st.columns(2)
    with col_obs:
        st.markdown(f"""
<div style="background: linear-gradient(145deg, rgba(30,41,59,0.6), rgba(15,23,42,0.7)); 
     border: 1px solid rgba(56,189,248,0.2); border-radius: 14px; padding: 18px; height: 100%;">
    <div style="font-size: 0.95rem; font-weight: 600; color: #38bdf8; margin-bottom: 10px;">
        🔍 技术观察
    </div>
    <div style="color: #cbd5e1; font-size: 0.82rem; line-height: 1.6;">
        {obs_html}
    </div>
</div>
""", unsafe_allow_html=True)

    with col_strat:
        st.markdown(f"""
<div style="background: linear-gradient(145deg, rgba(30,41,59,0.6), rgba(15,23,42,0.7)); 
     border: 1px solid rgba(239,68,68,0.2); border-left: 3px solid #ef4444; border-radius: 14px; padding: 18px; height: 100%;">
    <div style="font-size: 0.95rem; font-weight: 600; color: #f87171; margin-bottom: 10px;">
        📌 策略建议
    </div>
    <div style="color: #cbd5e1; font-size: 0.82rem; line-height: 1.6;">
        {strat_html}
    </div>
    <div style="color: #64748b; font-size: 0.7rem; margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px;">
        ⚠️ 算法自动生成，仅供参考，不构成投资建议
    </div>
</div>
""", unsafe_allow_html=True)


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
