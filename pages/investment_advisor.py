"""
🎯 AI智能投顾页面
Mock data replaced → 使用真实自选股数据
"""
import streamlit as st
import plotly.graph_objects as go
from modules.ai.investment_advisor import InvestmentAdvisor, RiskTolerance, InvestmentStyle, InvestmentHorizon
from modules.data_loader import fetch_kline
from pages import load_watchlist
from utils.export import render_export_panel

investment_advisor = InvestmentAdvisor()


def render(L):
    from components.ui_components import page_header, stock_selector
    page_header("AI 智能投顾", icon="🎯")

    tab1, tab2, tab3, tab4 = st.tabs(["用户画像", "资产配置", "风险评估", "投资建议"])

    user_id = st.session_state.get('user_id', 'default_user')

    with tab1:
        st.subheader("用户风险画像")
        profile = investment_advisor.get_profile(user_id)

        with st.form("user_profile"):
            col1, col2 = st.columns(2)
            with col1:
                age = st.slider("年龄", 18, 80, profile.age if profile else 35)
                income = st.number_input("年收入(万元)", value=profile.annual_income if profile else 50, step=10)
                assets = st.number_input("可投资资产(万元)", value=profile.investable_assets if profile else 100, step=10)
            with col2:
                risk_options = ["保守型", "稳健型", "平衡型", "进取型", "激进型"]
                risk_values = ["conservative", "moderate", "balanced", "aggressive", "speculative"]
                risk = st.selectbox("风险承受能力", risk_options,
                                   index=2 if not profile else risk_values.index(profile.risk_tolerance.value))

                style_options = ["价值投资", "成长投资", "指数投资", "股息投资", "动量投资", "平衡型"]
                style_values = ["value", "growth", "index", "dividend", "momentum", "balanced"]
                style = st.selectbox("投资风格", style_options,
                                    index=5 if not profile else style_values.index(profile.investment_style.value))

                horizon_options = ["短期(<1年)", "中期(1-3年)", "长期(>3年)"]
                horizon_values = ["short", "medium", "long"]
                horizon = st.selectbox("投资期限", horizon_options,
                                      index=1 if not profile else horizon_values.index(profile.horizon.value))

            submitted = st.form_submit_button("保存画像", type="primary")

            if submitted:
                risk_map = dict(zip(risk_options, risk_values))
                style_map = dict(zip(style_options, style_values))
                horizon_map = dict(zip(horizon_options, horizon_values))

                investment_advisor.create_profile(
                    user_id=user_id, age=age,
                    annual_income=income, investable_assets=assets,
                    risk_tolerance=RiskTolerance(risk_map[risk]),
                    investment_style=InvestmentStyle(style_map[style]),
                    horizon=InvestmentHorizon(horizon_map[horizon])
                )
                st.success("用户画像已保存")

    with tab2:
        st.subheader("资产配置建议")

        if profile or investment_advisor.get_profile(user_id):
            allocation = investment_advisor.recommend_allocation(user_id)

            col1, col2 = st.columns([1, 1])
            with col1:
                st.write("**大类资产配置**")
                labels = ['股票', '债券', '现金', '另类']
                values = [allocation.stocks_pct, allocation.bonds_pct, allocation.cash_pct, allocation.alternatives_pct]
                colors = ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6']

                fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.4, marker_colors=colors)])
                fig.update_layout(
                    template="plotly_dark" if st.session_state['theme'] == 'dark' else "plotly_white",
                    height=350, margin=dict(l=0, r=0, t=30, b=0), showlegend=True
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.write("**配置详情**")
                st.metric("股票类资产", f"{allocation.stocks_pct}%")
                st.metric("债券类资产", f"{allocation.bonds_pct}%")
                st.metric("现金及等价物", f"{allocation.cash_pct}%")
                st.metric("另类投资", f"{allocation.alternatives_pct}%")

                st.write("**股票细分**")
                st.caption(f"大盘: {allocation.large_cap_pct}% | 中盘: {allocation.mid_cap_pct}% | 小盘: {allocation.small_cap_pct}%")
                st.caption(f"国内: {allocation.domestic_pct}% | 国际: {allocation.international_pct}%")
        else:
            st.info("请先创建用户画像")

    with tab3:
        st.subheader("组合风险评估")

        if profile or investment_advisor.get_profile(user_id):
            # 使用用户真实自选股替代硬编码持仓
            watchlist = load_watchlist()
            if watchlist:
                # 均分持仓
                weight = 100 // len(watchlist) if watchlist else 0
                holdings = {s: weight for s in watchlist}
            else:
                holdings = {st.session_state['selected_stock']: 100}

            st.caption(f"💼 基于您的自选股 ({len(holdings)} 只) 进行风险评估")
            risk = investment_advisor.assess_portfolio_risk(user_id, holdings)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("综合风险评分", f"{risk.overall_risk_score:.1f}")
            col2.metric("风险等级", risk.risk_level)
            col3.metric("预估波动率", f"{risk.portfolio_volatility:.2f}%")
            col4.metric("预估最大回撤", f"{risk.max_drawdown_estimate:.2f}%")

            st.write("**风险建议**:")
            for rec in risk.recommendations:
                st.write(f"- {rec}")

            categories = ['波动率', '集中度', '流动性', '信用风险', '市场风险']
            values = [min(risk.portfolio_volatility, 100), risk.concentration_risk, 50, 50, 50]

            fig = go.Figure(data=go.Scatterpolar(
                r=values + [values[0]], theta=categories + [categories[0]],
                fill='toself', line=dict(color='#ef4444', width=2),
                fillcolor='rgba(239, 68, 68, 0.3)'
            ))
            fig.update_layout(
                template="plotly_dark" if st.session_state['theme'] == 'dark' else "plotly_white",
                polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                height=350, margin=dict(l=0, r=0, t=30, b=0), showlegend=False
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("请先创建用户画像")

    with tab4:
        st.subheader("个性化投资建议")
        symbol = stock_selector(key_suffix="advisor")

        col1, col2 = st.columns(2)

        with col1:
            st.write("**投资建议**")
            if st.button("获取建议", type="primary"):
                if profile or investment_advisor.get_profile(user_id):
                    # 获取真实价格数据
                    full_sym = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
                    kline = fetch_kline(full_sym, period='daily', datalen=5)
                    if not kline.empty and len(kline) >= 2:
                        latest = kline.iloc[-1]
                        prev = kline.iloc[-2]
                        current_data = {
                            'price': float(latest['收盘']),
                            'change_pct': float((latest['收盘'] / prev['收盘'] - 1) * 100),
                            'volume_change': float(latest['成交量'] / prev['成交量']) if prev['成交量'] > 0 else 1.0
                        }
                    else:
                        current_data = {'price': 0, 'change_pct': 0, 'volume_change': 1.0}
                    advice = investment_advisor.advise_position(user_id, symbol, current_data)

                    st.metric("当前仓位", f"{advice.current_position}%")
                    st.metric("建议仓位", f"{advice.suggested_position}%")
                    st.metric("建议操作", advice.action.upper())
                    st.write(f"**操作比例**: {advice.action_pct}%")
                    st.write(f"**理由**: {advice.reasoning}")
                else:
                    st.warning("请先创建用户画像")

        with col2:
            st.write("**投资计划书**")
            if st.button("生成计划书", type="primary"):
                if profile or investment_advisor.get_profile(user_id):
                    plan = investment_advisor.generate_investment_plan(user_id)
                    st.markdown(plan)
                    render_export_panel(report_text=plan, symbol="portfolio", key_prefix="inv_plan")
                else:
                    st.warning("请先创建用户画像")
