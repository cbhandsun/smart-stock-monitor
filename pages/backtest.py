"""
📊 回测引擎页面 — V2.0
参数面板 + 结果仪表盘 + 跨页导航
"""
import streamlit as st
try:
    from utils.html_renderer import render_html
except ImportError:
    render_html = lambda h: st.html(h)
import datetime as dt
import pandas as pd
from modules.data_loader import fetch_kline
from modules.backtest.backtest_engine import BacktestEngine, StrategyTemplate
from components.ui_components import page_header, stock_selector, nav_to_page, info_card

# 条件导入
try:
    from utils.charts import create_performance_chart, create_drawdown_chart, create_backtest_trade_chart
except ImportError:
    create_performance_chart = None
    create_drawdown_chart = None
    create_backtest_trade_chart = None


def render(L):
    page_header("回测引擎", subtitle="历史策略验证", icon="📊")

    # ---- 参数面板 (Expander) ----
    with st.expander("⚙️ 回测参数设置", expanded=True):
        with st.form("backtest_config"):
            col1, col2, col3 = st.columns(3)
            with col1:
                # 支持以逗号分隔的多标的代码输入
                current_stock = st.session_state.get('selected_stock', '601318')
                symbols_input = st.text_input(
                    "📋 投资组合标的 (以逗号分隔)", 
                    value=current_stock,
                    help="请输入A股股票代码，支持输入多只股票，用半角逗号 `,` 分隔。例如：601318,000001。系统会自动获取对应行情数据并等权重构建资产组合。"
                )
                strategy = st.selectbox(
                    "📋 策略", 
                    ["均线交叉", "RSI策略"],
                    help="选择用于验证的量化策略类型。目前支持【均线交叉】（经典SMA快慢线金叉死叉）与【RSI策略】（超买超卖动量反转）。"
                )
            with col2:
                start_date = st.date_input(
                    "📅 开始日期", 
                    dt.date(2024, 1, 1),
                    help="回测历史区间的起点，系统会自动追溯并对齐此日期起的所有标的历史K线价格。"
                )
                end_date = st.date_input(
                    "📅 结束日期", 
                    dt.date.today(),
                    help="回测历史区间的终点，默认为当前最新交易日。"
                )
            with col3:
                initial_cash = st.number_input(
                    "💰 初始资金", 
                    value=100000, 
                    step=10000,
                    help="本金模拟额度，主要作为仓位计算与杠杆比例计算的静态分母基数。"
                )
                commission = st.number_input(
                    "📊 手续费率", 
                    value=0.0003, 
                    format="%.4f",
                    help="策略运行中模拟买入和卖出的单边摩擦成本费率（例如 0.0003 即万分之三，包含了券商佣金及交易所过户规费）。"
                )

            submitted = st.form_submit_button("🚀 开始回测", type="primary", use_container_width=True)

    if submitted:
        with st.status("正在运行回测...", expanded=True) as status:
            # 解析多代码列表
            symbols_list = [s.strip() for s in symbols_input.split(",") if s.strip()]
            st.write(f"📈 组合标的: {', '.join(symbols_list)} | 策略: {strategy}")
            st.write(f"📅 周期: {start_date} → {end_date}")

            data_dict = {}
            for sym in symbols_list:
                full_symbol = f"sh{sym}" if sym.startswith('6') else f"sz{sym}"
                kline = fetch_kline(full_symbol)
                if not kline.empty:
                    data_dict[sym] = kline

            if data_dict:
                engine = BacktestEngine(initial_cash=initial_cash, commission_rate=commission)

                if strategy == "均线交叉":
                    engine.set_strategy(*StrategyTemplate.ma_cross_strategy(5, 20))
                else:
                    engine.set_strategy(*StrategyTemplate.rsi_strategy(30, 70))

                result = engine.run(data_dict, start_date.strftime('%Y-%m-%d'),
                                    end_date.strftime('%Y-%m-%d'))

                if result:
                    status.update(label="✅ 回测完成！", state="complete")

                    # 保存结果到数据库
                    try:
                        from database.models import get_db
                        db = get_db()
                        import uuid
                        result_id = f"backtest_{uuid.uuid4().hex[:12]}"
                        user_id = st.session_state.get('user_id', 'default_user')
                        symbols_metadata = {
                            "list": symbols_list,
                            "alpha": result.get('alpha'),
                            "beta": result.get('beta'),
                            "sortino": result.get('sortino_ratio'),
                            "info_ratio": result.get('info_ratio'),
                            "tracking_error": result.get('tracking_error')
                        }
                        db.save_backtest_result(
                            result_id=result_id,
                            user_id=user_id,
                            strategy_name=strategy,
                            symbols=symbols_metadata,
                            start_date=dt.datetime.combine(start_date, dt.time.min),
                            end_date=dt.datetime.combine(end_date, dt.time.min),
                            initial_cash=float(initial_cash),
                            final_value=float(result['final_value']),
                            total_return=float(result['total_return']),
                            annual_return=float(result['annual_return']),
                            max_drawdown=float(result['max_drawdown']),
                            sharpe_ratio=float(result['sharpe_ratio']),
                            total_trades=int(result.get('total_trades', 0)),
                            daily_values=result['daily_values']
                        )
                    except Exception as db_err:
                        print("Failed to save backtest result to DB:", db_err)

                    # ---- 结果仪表盘 ----
                    st.markdown("### 📊 回测结果")

                    # 核心指标行 (第一行)
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

                    # 第一层风险指标 (第二行)
                    r2c1, r2c2, r2c3 = st.columns(3)
                    r2c1.metric("夏普比率 (Sharpe)", f"{result['sharpe_ratio']:.2f}")
                    r2c2.metric("索提诺比率 (Sortino)", f"{result.get('sortino_ratio', 0.0):.2f}")
                    r2c3.metric("信息比率 (Info Ratio)", f"{result.get('info_ratio', 0.0):.2f}")

                    # 跑赢大盘超额指标 (第三行)
                    r3c1, r3c2, r3c3 = st.columns(3)
                    r3c1.metric("阿尔法值 (Alpha)", f"{result.get('alpha', 0.0):+.2f}%")
                    r3c2.metric("贝塔值 (Beta)", f"{result.get('beta', 1.0):.2f}")
                    r3c3.metric("胜率 & 交易数", f"{result.get('win_rate', 0.0):.1f}% ({result.get('total_trades', 0)}次)")

                    # 常见量化指标科普与风险归因说明
                    with st.expander("📖 常见量化风险归因指标说明（点击展开科普）", expanded=False):
                        st.markdown("""
                        ##### 📈 基础收益与风险指标
                        - **总收益率 (Total Return)**: 策略在整个回测区间内获得的总资金增幅比例。公式：`(期末资产 - 期初资产) / 期初资产 * 100%`。
                        - **年化收益率 (Annualized Return)**: 将策略总收益率折算到按年化时间尺度的收益率，用于在不同周期的策略间对比。
                        - **最大回撤 (Max Drawdown)**: 回测期内资产净值从最高峰到最低谷的最大跌幅。是衡量策略极端下行风险的最重要指标。
                        
                        ##### ⚖️ 经典风险调整后收益指标
                        - **夏普比率 (Sharpe Ratio)**: 衡量单位**总风险**（以资产收益标准差衡量）所带来的超额回报。比率越高说明策略性价比越高。通常 $>1$ 为优秀，$>2$ 为极佳。
                        - **索提诺比率 (Sortino Ratio)**: 类似夏普比率，但分母只计算**下行波动率**（即忽略上行带来的“好风险”）。对有主动止损或非对称风险的策略评估更精准。
                        
                        ##### 🏛️ 现代投资组合理论归因 (以沪深 300 为基准)
                        - **阿尔法值 (Alpha, α)**: 衡量策略跑赢大盘的**绝对超额收益**。Alpha 越高，说明选股与择时的主动管理能力越强。
                        - **贝塔值 (Beta, β)**: 衡量策略相对于大盘波动的**敏感系数**。$\\beta = 1$ 表示与大盘波动一致；$\\beta > 1$ 说明弹性大（大盘涨跌时波动更剧烈）；$\\beta < 1$ 属于防御型组合。
                        - **信息比率 (Information Ratio, IR)**: 衡量单位**主动跟踪误差**所能带来的超额收益，体现策略战胜大盘的稳定性和持续性。
                        """)

                    # ---- 交互式回测可视化大屏 ----
                    tab_perf, tab_signals, tab_details = st.tabs([
                        "📈 资产净值与回撤", 
                        "🕯️ 价格走势与买卖信号", 
                        "📋 详细成交明细表"
                    ])

                    theme = st.session_state.get('theme', 'dark')

                    with tab_perf:
                        if result.get('daily_values') and create_performance_chart:
                            st.markdown("##### 净值曲线走势")
                            fig_perf = create_performance_chart(result['daily_values'], theme=theme)
                            st.plotly_chart(fig_perf, use_container_width=True)
                            
                        if result.get('daily_values') and create_drawdown_chart:
                            st.markdown("##### 回撤深度走势 (Drawdown)")
                            fig_dd = create_drawdown_chart(result['daily_values'], theme=theme)
                            st.plotly_chart(fig_dd, use_container_width=True)

                    with tab_signals:
                        if create_backtest_trade_chart and len(data_dict) == 1:
                            # 仅单股回测展示K线买卖信号
                            single_sym = list(data_dict.keys())[0]
                            st.markdown(f"##### {single_sym} K线走势与买卖点标记")
                            fig_trade = create_backtest_trade_chart(data_dict[single_sym], result.get('trades_list', []), theme=theme)
                            st.plotly_chart(fig_trade, use_container_width=True)
                        else:
                            st.info("💡 多资产投资组合回测下，请到'详细成交明细表'查看个股具体成交记录。价格买卖信号标记仅支持单股回测展示。")

                    with tab_details:
                        st.markdown("##### 成交明细流水")
                        trades_list = result.get('trades_list', [])
                        if trades_list:
                            trades_df = pd.DataFrame(trades_list)
                            trades_df.rename(columns={
                                'symbol': '股票代码',
                                'entry_date': '买入日期',
                                'exit_date': '卖出日期',
                                'direction': '交易方向',
                                'size': '交易数量',
                                'entry_price': '买入价',
                                'exit_price': '卖出价',
                                'pnl': '盈亏金额',
                                'return_pct': '收益率'
                            }, inplace=True)
                            
                            st.dataframe(
                                trades_df[['股票代码', '买入日期', '卖出日期', '交易方向', '买入价', '卖出价', '交易数量', '盈亏金额', '收益率']],
                                use_container_width=True,
                                column_config={
                                    '买入价': st.column_config.NumberColumn(format="%.2f元"),
                                    '卖出价': st.column_config.NumberColumn(format="%.2f元"),
                                    '盈亏金额': st.column_config.NumberColumn(format="%.2f元"),
                                    '收益率': st.column_config.NumberColumn(format="%.2f%%"),
                                }
                            )
                        else:
                            st.info("当前回测周期内没有产生任何成交记录。")

                    # ---- 策略摘要卡片 ----
                    st.html(f'''<div class="ssm-card" style="margin-top:12px;">
                        <div class="ssm-card-title">📋 策略摘要</div>
                        <div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:10px;
                             font-size:0.85rem; color:#cbd5e1; margin-top:8px;">
                            <div>标的数: <strong style="color:#f1f5f9">{len(symbols_list)}个</strong></div>
                            <div>策略: <strong style="color:#f1f5f9">{strategy}</strong></div>
                            <div>初始资金: <strong style="color:#f1f5f9">¥{initial_cash:,.0f}</strong></div>
                            <div>手续费率: <strong style="color:#f1f5f9">{commission:.4f}</strong></div>
                            <div>回测周期: <strong style="color:#f1f5f9">{start_date} → {end_date}</strong></div>
                            <div>CSI300 Beta基准: <strong style="color:#f1f5f9">{result.get('beta', 1.0):.2f}</strong></div>
                        </div>
                    </div>''')

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
