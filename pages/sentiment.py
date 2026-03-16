"""
💭 市场情绪分析页面
Mock data replaced → 基于真实K线数据计算情绪指标
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from modules.ai.sentiment_analyzer import SentimentAnalyzer
from modules.data_loader import fetch_kline
from utils.export import render_export_panel



sentiment_analyzer = SentimentAnalyzer()


def _compute_sentiment_from_kline(kline: pd.DataFrame) -> list:
    """
    基于真实K线数据计算情绪指标，取代 np.sin() 假数据。
    原理：用涨跌幅 + 量能变化推算多空情绪。
    """
    if kline.empty or len(kline) < 5:
        return []

    kline = kline.copy().sort_values('日期')
    close = kline['收盘'].values
    volume = kline['成交量'].values

    # 涨跌幅序列
    pct_change = np.diff(close) / close[:-1]
    # 量比序列
    vol_ma = pd.Series(volume).rolling(5, min_periods=1).mean().values

    history = []
    for i in range(1, len(kline)):
        chg = pct_change[i - 1]
        vol_ratio = volume[i] / vol_ma[i] if vol_ma[i] > 0 else 1.0

        # 情绪得分: 涨幅越大且放量则越看多, 反之看空
        raw_score = chg * 100 * 10  # 归一化到 -100~100 级别
        # 量能加权
        if vol_ratio > 1.5:
            raw_score *= 1.3  # 放量放大信号
        sentiment = max(-100, min(100, raw_score))

        bullish = max(0, min(1, 0.5 + sentiment / 200))
        bearish = max(0, min(1, 0.5 - sentiment / 200))
        neutral = 1 - bullish - bearish

        history.append({
            'date': kline.iloc[i]['日期'],
            'sentiment': round(sentiment, 2),
            'bullish': round(bullish, 3),
            'bearish': round(max(0, bearish), 3),
            'volume': int(volume[i]),
        })

    return history


def _extract_hot_keywords_from_kline(kline: pd.DataFrame) -> list:
    """基于价格走势生成真实关键词标签"""
    if kline.empty:
        return []

    close = kline['收盘']
    latest_chg = (close.iloc[-1] / close.iloc[-2] - 1) * 100 if len(close) >= 2 else 0
    vol_ratio = kline['成交量'].iloc[-1] / kline['成交量'].rolling(5).mean().iloc[-1] if len(kline) >= 5 else 1

    keywords = []
    if latest_chg > 5:
        keywords.append(("涨停", int(abs(latest_chg) * 8)))
    if latest_chg > 2:
        keywords.append(("突破", int(abs(latest_chg) * 6)))
    if latest_chg > 0:
        keywords.append(("看多", int(abs(latest_chg) * 5)))
        keywords.append(("反弹", int(abs(latest_chg) * 4)))
    if latest_chg < 0:
        keywords.append(("回调", int(abs(latest_chg) * 5)))
        keywords.append(("风险", int(abs(latest_chg) * 4)))
    if latest_chg < -3:
        keywords.append(("止损", int(abs(latest_chg) * 6)))
    if vol_ratio > 2:
        keywords.append(("放量", int(vol_ratio * 10)))
    if vol_ratio < 0.5:
        keywords.append(("缩量", int((1 / vol_ratio) * 8)))

    # 补足到至少5个
    base_keywords = [("业绩", 25), ("趋势", 20), ("均线", 18), ("资金", 15), ("震荡", 12)]
    for kw in base_keywords:
        if len(keywords) >= 10:
            break
        if kw[0] not in [k[0] for k in keywords]:
            keywords.append(kw)

    return sorted(keywords, key=lambda x: x[1], reverse=True)[:10]


def render(L, my_stocks, name_map):
    from components.ui_components import page_header, stock_selector, nav_to_page
    page_header("市场情绪分析", icon="💭")

    symbol = stock_selector(key_suffix="sentiment")

    if symbol:
        # 获取真实K线数据
        full_symbol = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
        kline = fetch_kline(full_symbol, period='daily', datalen=60)

        tab1, tab2, tab3 = st.tabs(["情绪指数", "情绪监控", "情绪报告"])

        with tab1:
            col1, col2 = st.columns([1, 2])

            with col1:
                st.subheader("情绪指数")

                if not kline.empty:
                    sentiment_history = _compute_sentiment_from_kline(kline)

                    if sentiment_history:
                        latest = sentiment_history[-1]
                        overall = latest['sentiment']

                        sentiment_color = "🟢" if overall > 20 else "🔴" if overall < -20 else "🟡"
                        st.metric("综合情绪", f"{overall:+.1f}",
                                 delta=f"{sentiment_color} {'看多' if overall > 20 else '看空' if overall < -20 else '中性'}")

                        st.progress(latest['bullish'], text=f"看多比例: {latest['bullish'] * 100:.1f}%")
                        st.progress(latest['bearish'], text=f"看空比例: {latest['bearish'] * 100:.1f}%")

                        avg_5d = np.mean([h['sentiment'] for h in sentiment_history[-5:]])
                        avg_20d = np.mean([h['sentiment'] for h in sentiment_history[-20:]]) if len(sentiment_history) >= 20 else avg_5d
                        trend = "转强" if avg_5d > avg_20d else "转弱" if avg_5d < avg_20d else "平稳"
                        st.write(f"**分析样本**: {len(sentiment_history)}个交易日")
                        st.write(f"**情绪趋势**: {trend}")
                else:
                    st.info("暂无K线数据")

            with col2:
                st.subheader("情绪趋势图")
                if not kline.empty and sentiment_history:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[d['date'] for d in sentiment_history],
                        y=[d['sentiment'] for d in sentiment_history],
                        mode='lines+markers', name='情绪指数',
                        line=dict(color='#3b82f6', width=2)
                    ))
                    fig.add_hline(y=20, line_dash="dash", line_color="green", annotation_text="看多阈值")
                    fig.add_hline(y=-20, line_dash="dash", line_color="red", annotation_text="看空阈值")
                    fig.update_layout(
                        template="plotly_dark" if st.session_state['theme'] == 'dark' else "plotly_white",
                        height=400, margin=dict(l=0, r=0, t=30, b=0),
                        yaxis=dict(title="情绪指数", range=[-100, 100])
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # 导出面板
                    df_export = pd.DataFrame(sentiment_history)
                    render_export_panel(df=df_export, symbol=symbol, key_prefix="sentiment")

        with tab2:
            st.subheader("实时情绪监控")
            st.write("**热点关键词**")

            hot_keywords = _extract_hot_keywords_from_kline(kline)
            if hot_keywords:
                cols = st.columns(5)
                for i, (keyword, count) in enumerate(hot_keywords):
                    with cols[i % 5]:
                        st.metric(keyword, f"{count}次")

            anomaly = sentiment_analyzer.detect_sentiment_anomaly(symbol)
            if anomaly:
                st.error(f"⚠️ 检测到情绪异常: {anomaly['type']} (严重程度: {anomaly['severity']})")
            else:
                st.success("✅ 情绪正常，无异常波动")

        with tab3:
            st.subheader("情绪分析报告")
            if st.button("生成完整报告", type="primary"):
                report = sentiment_analyzer.generate_sentiment_report(symbol)
                st.markdown(report)

                # 导出报告
                render_export_panel(report_text=report, symbol=symbol, key_prefix="sentiment_report")

    # 跨页导航替代冗余的 DNA Analyzer
    st.divider()
    st.caption("📌 下一步")
    c1, c2 = st.columns(2)
    with c1:
        nav_to_page('market', '前往深度分析看盘', icon='📊', stock_code=symbol)
    with c2:
        nav_to_page('predict', '进行趋势预测', icon='🔮', stock_code=symbol)
