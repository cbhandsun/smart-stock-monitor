"""
📊 回测引擎页面 — V2.0
参数面板 + 结果仪表盘 + 跨页导航
"""
import streamlit as st
import datetime as dt
from modules.data_loader import fetch_kline
from modules.backtest.backtest_engine import BacktestEngine, StrategyTemplate
from components.ui_components import page_header, stock_selector, nav_to_page, info_card

# 条件导入
try:
    from utils.charts import create_performance_chart
except ImportError:
    create_performance_chart = None


def render(L):
    page_header("回测引擎", subtitle="历史策略验证", icon="📊")

    # ---- 参数面板 (Expander) ----
    with st.expander("⚙️ 回测参数设置", expanded=True):
        with st.form("backtest_config"):
            col1, col2, col3 = st.columns(3)
            with col1:
                symbol = stock_selector(key_suffix="backtest")
                strategy = st.selectbox("📋 策略", ["均线交叉", "RSI策略"])
            with col2:
                start_date = st.date_input("📅 开始日期", dt.date(2024, 1, 1))
                end_date = st.date_input("📅 结束日期", dt.date.today())
            with col3:
                initial_cash = st.number_input("💰 初始资金", value=100000, step=10000)
                commission = st.number_input("📊 手续费率", value=0.0003, format="%.4f")

            submitted = st.form_submit_button("🚀 开始回测", type="primary", use_container_width=True)

    if submitted:
        with st.status("正在运行回测...", expanded=True) as status:
            st.write(f"📈 标的: {symbol} | 策略: {strategy}")
            st.write(f"📅 周期: {start_date} → {end_date}")

            full_symbol = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
            kline = fetch_kline(full_symbol)

            if not kline.empty:
                engine = BacktestEngine(initial_cash=initial_cash, commission_rate=commission)

                if strategy == "均线交叉":
                    engine.set_strategy(*StrategyTemplate.ma_cross_strategy(5, 20))
                else:
                    engine.set_strategy(*StrategyTemplate.rsi_strategy(30, 70))

                data_dict = {symbol: kline}
                result = engine.run(data_dict, start_date.strftime('%Y-%m-%d'),
                                    end_date.strftime('%Y-%m-%d'))

                if result:
                    status.update(label="✅ 回测完成！", state="complete")

                    # ---- 结果仪表盘 ----
                    st.markdown("### 📊 回测结果")

                    # 核心指标行 (颜色编码)
                    total_return = result['total_return']
                    ret_color = "normal" if total_return >= 0 else "inverse"

                    r1c1, r1c2, r1c3 = st.columns(3)
                    r1c1.metric("总收益率", f"{total_return:.2f}%",
                               delta="盈利" if total_return >= 0 else "亏损",
                               delta_color=ret_color)
                    r1c2.metric("年化收益率", f"{result['annual_return']:.2f}%",
                               delta_color=ret_color)
                    r1c3.metric("最大回撤", f"{result['max_drawdown']:.2f}%",
                               delta="风险可控" if abs(result['max_drawdown']) < 20 else "⚠️ 高风险",
                               delta_color="inverse" if abs(result['max_drawdown']) >= 20 else "off")

                    r2c1, r2c2, r2c3 = st.columns(3)
                    r2c1.metric("夏普比率", f"{result['sharpe_ratio']:.2f}")
                    r2c2.metric("胜率", f"{result.get('win_rate', 0):.1f}%")
                    r2c3.metric("总交易次数", f"{result.get('total_trades', 0)}")

                    # ---- 绩效曲线 ----
                    if result.get('daily_values') and create_performance_chart:
                        st.markdown("##### 📈 净值曲线")
                        fig = create_performance_chart(result['daily_values'],
                                                       theme=st.session_state['theme'])
                        st.plotly_chart(fig, use_container_width=True)

                    # ---- 策略摘要卡片 ----
                    st.markdown(f'''<div class="ssm-card" style="margin-top:12px;">
                        <div class="ssm-card-title">📋 策略摘要</div>
                        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;
                             font-size:0.85rem; color:#cbd5e1; margin-top:8px;">
                            <div>标的: <strong style="color:#f1f5f9">{symbol}</strong></div>
                            <div>策略: <strong style="color:#f1f5f9">{strategy}</strong></div>
                            <div>初始资金: <strong style="color:#f1f5f9">¥{initial_cash:,.0f}</strong></div>
                            <div>手续费率: <strong style="color:#f1f5f9">{commission:.4f}</strong></div>
                            <div>回测周期: <strong style="color:#f1f5f9">{start_date} → {end_date}</strong></div>
                            <div>数据点: <strong style="color:#f1f5f9">{len(kline)}</strong></div>
                        </div>
                    </div>''', unsafe_allow_html=True)

                else:
                    status.update(label="❌ 回测失败", state="error")
                    st.error("回测失败，请检查数据和参数")
            else:
                status.update(label="❌ 数据获取失败", state="error")
                st.error("无法获取股票数据")

    # ---- 跨页导航 ----
    st.divider()
    st.caption("📌 下一步")
    c1, c2 = st.columns(2)
    with c1:
        nav_to_page('predict', '进行趋势预测', icon='🔮')
    with c2:
        nav_to_page('market', '前往市场看盘', icon='📡')
