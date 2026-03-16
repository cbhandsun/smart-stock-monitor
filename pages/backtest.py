"""
📊 回测引擎页面
"""
import streamlit as st
import datetime as dt
from modules.data_loader import fetch_kline
from modules.backtest.backtest_engine import BacktestEngine, StrategyTemplate

# 条件导入
try:
    from utils.charts import create_performance_chart
except ImportError:
    create_performance_chart = None


def render(L):
    from components.ui_components import page_header, stock_selector
    page_header("回测引擎", icon="📊")

    with st.form("backtest_config"):
        col1, col2, col3 = st.columns(3)
        with col1:
            symbol = stock_selector(key_suffix="backtest")
            strategy = st.selectbox("策略", ["均线交叉", "RSI策略"])
        with col2:
            start_date = st.date_input("开始日期", dt.date(2024, 1, 1))
            end_date = st.date_input("结束日期", dt.date.today())
        with col3:
            initial_cash = st.number_input("初始资金", value=100000, step=10000)
            commission = st.number_input("手续费率", value=0.0003, format="%.4f")

        submitted = st.form_submit_button("开始回测", type="primary")

    if submitted:
        with st.spinner("正在运行回测..."):
            full_symbol = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
            kline = fetch_kline(full_symbol)

            if not kline.empty:
                engine = BacktestEngine(initial_cash=initial_cash, commission_rate=commission)

                if strategy == "均线交叉":
                    engine.set_strategy(*StrategyTemplate.ma_cross_strategy(5, 20))
                else:
                    engine.set_strategy(*StrategyTemplate.rsi_strategy(30, 70))

                data_dict = {symbol: kline}
                result = engine.run(data_dict, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))

                if result:
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    col1.metric("总收益率", f"{result['total_return']:.2f}%")
                    col2.metric("年化收益率", f"{result['annual_return']:.2f}%")
                    col3.metric("最大回撤", f"{result['max_drawdown']:.2f}%")
                    col4.metric("夏普比率", f"{result['sharpe_ratio']:.2f}")
                    col5.metric("胜率", f"{result.get('win_rate', 0):.1f}%")
                    col6.metric("总交易次数", f"{result.get('total_trades', 0)}")

                    if result.get('daily_values') and create_performance_chart:
                        fig = create_performance_chart(result['daily_values'], theme=st.session_state['theme'])
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("回测失败，请检查数据")
            else:
                st.error("无法获取股票数据")
