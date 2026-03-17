"""
📁 组合管理页面 — V2.0
双列布局 + 持仓卡片 + 空状态引导 + 统计仪表盘
"""
import streamlit as st
import pandas as pd
from modules.portfolio.watchlist_manager import WatchlistManager
from components.ui_components import page_header, info_card, empty_state, nav_to_page

watchlist_manager = WatchlistManager()


def render(L):
    page_header("组合管理", icon="📁")

    portfolios = watchlist_manager.list_portfolios()

    # ---- 统计仪表盘 ----
    total_stocks = sum(len(p.stocks) for p in portfolios) if portfolios else 0
    m1, m2, m3 = st.columns(3)
    with m1:
        info_card("组合总数", str(len(portfolios)), icon="📂", color="#3b82f6")
    with m2:
        info_card("持股总数", str(total_stocks), icon="📊", color="#10b981")
    with m3:
        latest = max((p.created_at for p in portfolios), default="—") if portfolios else "—"
        info_card("最近创建", str(latest)[:10] if latest != "—" else "—", icon="🕐", color="#f59e0b")

    st.markdown("")  # spacing

    # ---- 主体: 组合列表 | 创建面板 ----
    tab1, tab2 = st.tabs(["📂 我的组合", "➕ 创建组合"])

    with tab1:
        if portfolios:
            for portfolio in portfolios:
                with st.expander(f"📂 {portfolio.name} ({len(portfolio.stocks)} 只股票)", expanded=False):
                    # 描述
                    if portfolio.description:
                        st.caption(f"💬 {portfolio.description}")

                    if portfolio.stocks:
                        stock_data = []
                        for s in portfolio.stocks:
                            _get = (lambda k, d='': s.get(k, d)) if isinstance(s, dict) else (lambda k, d='': getattr(s, k, d))
                            tags = _get('tags', [])
                            stock_data.append({
                                "代码": _get('symbol'), "名称": _get('name'),
                                "数量": _get('quantity', 0), "成本": _get('avg_cost', 0),
                                "标签": ", ".join(tags) if tags else "-",
                                "备注": _get('notes') or "-"
                            })
                        df = pd.DataFrame(stock_data)
                        st.dataframe(
                            df,
                            use_container_width=True,
                            column_config={
                                "成本": st.column_config.NumberColumn("成本", format="¥ %.2f"),
                                "数量": st.column_config.NumberColumn("数量", format="%d 股"),
                            },
                            hide_index=True
                        )
                    else:
                        st.info("💡 该组合暂无持仓，前往市场页面添加股票")

                    # 操作按钮行
                    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
                    with btn_col1:
                        nav_to_page('market', '前往选股', icon='📡')
                    with btn_col2:
                        st.empty()  # spacer
                    with btn_col3:
                        # 二次确认删除
                        confirm_key = f"confirm_del_{portfolio.id}"
                        if st.session_state.get(confirm_key, False):
                            if st.button("⚠️ 确认删除", key=f"do_del_{portfolio.id}",
                                        type="primary", use_container_width=True):
                                watchlist_manager.delete_portfolio(portfolio.id)
                                st.session_state[confirm_key] = False
                                st.rerun()
                        else:
                            if st.button("🗑️ 删除", key=f"del_port_{portfolio.id}",
                                        use_container_width=True):
                                st.session_state[confirm_key] = True
                                st.rerun()
        else:
            empty_state(
                icon="📂",
                title="还没有组合",
                description="创建第一个投资组合，开始管理您的持仓",
            )

    with tab2:
        with st.form("create_portfolio"):
            name = st.text_input("📌 组合名称", placeholder="如：核心持仓、短线仓")
            description = st.text_area("📝 组合描述", placeholder="简要描述组合的投资策略和目标...",
                                       height=100)
            submitted = st.form_submit_button("✨ 创建组合", type="primary", use_container_width=True)

            if submitted and name:
                watchlist_manager.create_portfolio(name, description)
                st.success(f"✅ 组合 '{name}' 创建成功！")
                st.balloons()
                st.rerun()
            elif submitted:
                st.warning("请输入组合名称")

    # 底部导航
    st.divider()
    st.caption("📌 下一步")
    c1, c2 = st.columns(2)
    with c1:
        nav_to_page('market', '前往市场选股', icon='📡')
    with c2:
        nav_to_page('investment_advisor', '获取资产配置建议', icon='🎯')
