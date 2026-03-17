"""
🔮 预测分析页面
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from modules.data_loader import fetch_kline
from modules.ai.predictive_analysis import PredictiveAnalyzer
from components.ui_components import page_header, stock_selector, nav_to_page

predictor = PredictiveAnalyzer()


def render(L):
    page_header("预测分析", icon="🔮")

    symbol = stock_selector(key_suffix="predict")

    if symbol:
        full_symbol = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
        kline = fetch_kline(full_symbol)

        if not kline.empty:
            tab1, tab2, tab3 = st.tabs(["趋势预测", "风险评估", "支撑阻力"])

            with tab1:
                method_map = {"线性回归": "linear", "多项式": "poly", "随机森林": "rf", "梯度提升(GBDT)": "gbdt"}
                method_label = st.selectbox("预测方法", list(method_map.keys()), index=3)
                method = method_map[method_label]
                days = st.slider("预测天数", 1, 30, 5)

                if st.button("开始预测", type="primary"):
                    with st.status("🔮 正在训练模型...") as status:
                        st.write("📐 构建技术特征 (MA/RSI/MACD/波动率/动量/量比)...")
                        result = predictor.trend_prediction(kline, days=days, method=method)
                        if 'error' not in result:
                            status.update(label=f"✅ 预测完成 — 方向准确率 {result.get('direction_accuracy', '?')}%",
                                         state="complete")
                        else:
                            status.update(label="❌ 预测失败", state="error")

                    if 'error' not in result:
                        col1, col2, col3 = st.columns(3)
                        change_val = result['expected_change']
                        change_color = "#ef4444" if change_val >= 0 else "#10b981"
                        col1.metric("当前价格", f"{result['current_price']:.2f}")
                        col2.metric("预测价格", f"{result['predicted_price']:.2f}")
                        col3.metric("预期涨跌", f"{change_val:+.2f}%")

                        # 置信度 + 方向准确率
                        conf = result['confidence']
                        dir_acc = result.get('direction_accuracy', 0)
                        c_col1, c_col2 = st.columns(2)
                        with c_col1:
                            st.progress(conf / 100, text=f"综合置信度: {conf:.1f}%")
                        with c_col2:
                            st.progress(dir_acc / 100, text=f"方向准确率: {dir_acc:.1f}%")

                        fig = go.Figure()
                        dates = list(kline['日期'])
                        prices = list(kline['收盘'])
                        fig.add_trace(go.Scatter(x=dates, y=prices, name='历史价格', line=dict(color='#3b82f6')))

                        future_dates = pd.date_range(start=dates[-1], periods=days + 1)[1:]
                        fig.add_trace(go.Scatter(
                            x=future_dates, y=result['predictions'],
                            name='预测价格', line=dict(color='#10b981', dash='dash', width=2.5)
                        ))
                        fig.update_layout(template="plotly_dark", height=400)
                        st.plotly_chart(fig, use_container_width=True)

                        # 跨页联动
                        st.divider()
                        st.caption("📌 下一步")
                        c1, c2 = st.columns(2)
                        with c1:
                            nav_to_page('backtest', '用回测引擎验证策略', icon='📊', stock_code=symbol)
                        with c2:
                            nav_to_page('market', '前往深度分析看盘', icon='📡', stock_code=symbol)
                    else:
                        st.error(result['error'])

            with tab2:
                if st.button("评估风险", type="primary"):
                    result = predictor.risk_assessment(kline)

                    if 'error' not in result:
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("波动率", f"{result['volatility']:.2f}%")
                        col2.metric("最大回撤", f"{result['max_drawdown']:.2f}%")
                        col3.metric("下行风险", f"{result['downside_risk']:.2f}%")
                        col4.metric("风险等级", result['risk_level'])
                        st.progress(result['risk_score'] / 100, text=f"风险评分: {result['risk_score']}")
                    else:
                        st.error(result['error'])

            with tab3:
                if st.button("计算支撑阻力", type="primary"):
                    result = predictor.support_resistance(kline)

                    if 'error' not in result:
                        col1, col2, col3 = st.columns(3)
                        col1.metric("当前价格", f"{result['current_price']:.2f}")
                        col2.metric("阻力位", f"{result['resistance']:.2f}")
                        col3.metric("支撑位", f"{result['support']:.2f}")

                        st.write("斐波那契回撤位:")
                        fib_cols = st.columns(3)
                        fib_cols[0].metric("38.2%", f"{result['fib_382']:.2f}")
                        fib_cols[1].metric("50%", f"{result['fib_500']:.2f}")
                        fib_cols[2].metric("61.8%", f"{result['fib_618']:.2f}")
                    else:
                        st.error(result['error'])
        else:
            st.error("无法获取股票数据")

