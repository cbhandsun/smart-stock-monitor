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


def render_dna_analyzer(L, my_stocks, name_map, default_target=None):
    """
    渲染 DNA Analyzer (可嵌入任意页面)
    :param L: 语言字典
    :param my_stocks: 当前用户的关注列表 list[str]
    :param name_map: 代码到名称的映射 dict
    :param default_target: 默认选中的股票代码
    """
    st.divider()
    st.header(L.get('dna_analysis', '🧬 Stock DNA Analysis'))

    # If the default target isn't in my_stocks, temporarily append it for the dropdown
    target = default_target if default_target else st.session_state.get('selected_stock', '601318')
    if target not in my_stocks:
        my_stocks_dropdown = [target] + my_stocks
        # Also ensure we have its name mapped
        if target not in name_map:
            new_names = get_stock_names_batch([target])
            name_map.update(new_names)
    else:
        my_stocks_dropdown = my_stocks

    sel_stock = st.selectbox(
        "Decision Target", 
        my_stocks_dropdown, 
        index=my_stocks_dropdown.index(target) if target in my_stocks_dropdown else 0,
        format_func=lambda x: f"{x} {name_map.get(x, '')}"
    )
    st.session_state['selected_stock'] = sel_stock

    # 时间周期选择器
    st.markdown(f"<div style='color:#a3a8b8; font-size:0.9rem; margin-bottom: 8px; font-weight: 500;'>⏱️ {L.get('time_period', 'Time Period')}</div>", unsafe_allow_html=True)
    period_cols = st.columns(8)
    periods = ['1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly']
    period_labels = ['1分', '5分', '15分', '30分', '60分', '日线', '周线', '月线']

    if 'selected_period' not in st.session_state:
        st.session_state['selected_period'] = 'daily'

    for i, (period, label) in enumerate(zip(periods, period_labels)):
        with period_cols[i]:
            if st.button(label, key=f"period_{period}_{id(render_dna_analyzer)}",
                        type="primary" if st.session_state['selected_period'] == period else "secondary",
                        use_container_width=True):
                st.session_state['selected_period'] = period
                st.rerun()

    # 技术指标选择
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:#a3a8b8; font-size:0.9rem; margin-bottom: 8px; font-weight: 500;'>📊 {L.get('indicators', 'Indicators')}</div>", unsafe_allow_html=True)
    indicator_cols = st.columns(6)
    available_indicators = {'MA': '均线', 'BB': '布林带', 'MACD': 'MACD', 'KDJ': 'KDJ', 'RSI': 'RSI', 'CCI': 'CCI'}

    if 'selected_indicators' not in st.session_state:
        st.session_state['selected_indicators'] = ['MA']

    for i, (key, label) in enumerate(available_indicators.items()):
        with indicator_cols[i]:
            is_selected = key in st.session_state['selected_indicators']
            if st.button(label, key=f"ind_{key}_{id(render_dna_analyzer)}",
                        type="primary" if is_selected else "secondary",
                        use_container_width=True):
                if is_selected:
                    st.session_state['selected_indicators'].remove(key)
                else:
                    st.session_state['selected_indicators'].append(key)
                st.rerun()

    # 获取数据
    selected_period = st.session_state.get('selected_period', 'daily')
    full_symbol = "sh" + sel_stock if sel_stock.startswith('6') else "sz" + sel_stock
    kline = fetch_kline(full_symbol, period=selected_period, datalen=100)

    # 计算扩展技术指标
    if not kline.empty and calculate_all_indicators:
        kline = calculate_all_indicators(kline)

    f_data = get_financial_health_score(sel_stock) if get_financial_health_score else None
    q_metrics = calculate_metrics(kline) if calculate_metrics else {}

    # 扩展指标展示
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    fin_score = f_data.get('score', 50) if f_data else 50
    fin_source = f_data.get('source', '') if f_data else ''
    m1.metric(L.get('fin_health', 'Financial Health'), f"{fin_score}%", delta=fin_source if fin_source else None, delta_color="off")
    m2.metric("RSI(14)", f"{q_metrics.get('rsi', 0):.1f}")
    m3.metric(L.get('ann_vol', 'Volatility'), f"{q_metrics.get('volatility_ann', 0):.1f}%")

    bb_width = q_metrics.get('bb_width', 0)
    bb_pos = "中轨附近"
    if q_metrics.get('bb_percent', 50) > 80:
        bb_pos = "上轨附近⚠️"
    elif q_metrics.get('bb_percent', 50) < 20:
        bb_pos = "下轨附近💡"
    m4.metric("布林带", f"{bb_width:.1f}%", delta=bb_pos, delta_color="off")

    kdj_k = q_metrics.get('kdj_k', 50)
    kdj_d = q_metrics.get('kdj_d', 50)
    kdj_signal = "金叉" if kdj_k > kdj_d and kdj_k < 50 else "死叉" if kdj_k < kdj_d else "整理"
    m5.metric(f"KDJ(K:{kdj_k:.1f})", f"D:{kdj_d:.1f}", delta=kdj_signal,
              delta_color="normal" if kdj_signal == "金叉" else "inverse")

    dmi_adx = q_metrics.get('dmi_adx', 0)
    adx_strength = "强趋势" if dmi_adx > 40 else "弱趋势" if dmi_adx < 20 else "震荡"
    m6.metric(f"ADX({dmi_adx:.1f})", adx_strength)

    if f_data and f_data.get('analysis'):
        st.caption(f"📊 {f_data['analysis']}")

    # Chart and AI Analysis
    chart_col, ai_col = st.columns([2, 1])
    with chart_col:
        if not kline.empty and render_tv_chart:
            indicators_to_show = []
            selected_indicators = st.session_state.get('selected_indicators', ['MA'])

            if 'MA' in selected_indicators:
                indicators_to_show.extend(['MA5', 'MA20', 'MA60'])
            if 'BB' in selected_indicators and 'BB_Upper' in kline.columns:
                indicators_to_show.extend(['BB_Upper', 'BB_Middle', 'BB_Lower'])

            theme_str = st.session_state.get('theme', 'dark')
            render_tv_chart(kline, height=450, theme=theme_str, indicators=indicators_to_show)

            # 显示副图指标
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

    with ai_col:
        c_refresh, c_status = st.columns([1, 2])
        with c_refresh:
            if st.button("🔄 刷新数据", key=f"refresh_{id(render_dna_analyzer)}", use_container_width=True):
                st.cache_data.clear()
                st.toast("数据已刷新", icon="✨")
                st.rerun()
        with c_status:
            st.caption(f"数据时间: {datetime.datetime.now().strftime('%H:%M:%S')}")

        st.divider()

        cached, is_cached = load_cached_report(sel_stock)

        if is_cached:
            st.success("📄 已有今日 AI 报告", icon="✅")
        else:
            st.info("🤖 点击生成 AI 分析报告", icon="💡")

        if st.button(L.get('invoke_ai', 'Invoke AI'), key=f"invoke_ai_{id(render_dna_analyzer)}", type="primary", use_container_width=True):
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
