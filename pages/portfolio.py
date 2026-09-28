"""
📁 组合管理页面 — V2.0
双列布局 + 持仓卡片 + 空状态引导 + 统计仪表盘
"""

import streamlit as st
import pandas as pd
from modules.portfolio.watchlist_manager import WatchlistManager
from components.ui_components import page_header, info_card, empty_state, nav_to_page


def render(L):
    watchlist_manager = WatchlistManager()
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
        latest = (
            max((p.created_at for p in portfolios), default="—") if portfolios else "—"
        )
        info_card(
            "最近创建",
            str(latest)[:10] if latest != "—" else "—",
            icon="🕐",
            color="#f59e0b",
        )

    st.markdown("")  # spacing

    # ---- 主体: 组合列表 | 创建面板 ----
    tab1, tab2, tab3 = st.tabs(["📂 我的组合", "➕ 创建组合", "🗄️ 归档与回收站"])

    with tab1:
        if portfolios:
            for idx, portfolio in enumerate(portfolios):
                with st.expander(
                    f"📂 {portfolio.name} ({len(portfolio.stocks)} 只股票)",
                    expanded=False,
                ):
                    # 描述
                    if portfolio.description:
                        st.caption(f"💬 {portfolio.description}")

                    if portfolio.stocks:
                        stock_data = []
                        for s in portfolio.stocks:
                            _get = (
                                (lambda k, d="": s.get(k, d))
                                if isinstance(s, dict)
                                else (lambda k, d="": getattr(s, k, d))
                            )
                            tags = _get("tags", [])
                            stock_data.append(
                                {
                                    "代码": _get("symbol"),
                                    "名称": _get("name"),
                                    "数量": _get("quantity", 0),
                                    "成本": _get("avg_cost", 0),
                                    "标签": ", ".join(tags) if tags else "-",
                                    "备注": _get("notes") or "-",
                                }
                            )
                        df = pd.DataFrame(stock_data)
                        st.dataframe(
                            df,
                            use_container_width=True,
                            column_config={
                                "成本": st.column_config.NumberColumn(
                                    "成本", format="¥ %.2f"
                                ),
                                "数量": st.column_config.NumberColumn(
                                    "数量", format="%d 股"
                                ),
                            },
                            hide_index=True,
                        )
                        st.download_button(
                            "⬇️ 导出组合 CSV",
                            data=df.to_csv(index=False).encode("utf-8-sig"),
                            file_name=f"portfolio-{portfolio.id}.csv",
                            mime="text/csv",
                            key=f"export_{portfolio.id}",
                            use_container_width=True,
                        )
                    else:
                        st.info(
                            "💡 该组合暂无持仓，可在下方直接添加，或前往市场先加入默认自选。"
                        )

                    with st.expander(
                        "➕ 添加股票到此组合", expanded=not portfolio.stocks
                    ):
                        with st.form(f"add_stock_{portfolio.id}"):
                            add_col1, add_col2 = st.columns(2)
                            with add_col1:
                                symbol = st.text_input(
                                    "股票代码", placeholder="例如 600519", max_chars=6
                                )
                                stock_name = st.text_input(
                                    "股票名称（可选）", max_chars=100
                                )
                            with add_col2:
                                quantity = st.number_input(
                                    "持仓数量", min_value=0, step=100, value=0
                                )
                                avg_cost = st.number_input(
                                    "平均成本", min_value=0.0, step=0.01, value=0.0
                                )
                            notes = st.text_input("备注（可选）", max_chars=500)
                            add_submitted = st.form_submit_button(
                                "添加到当前组合",
                                type="primary",
                                use_container_width=True,
                            )
                        if add_submitted:
                            try:
                                watchlist_manager.add_stock(
                                    portfolio.id,
                                    symbol=symbol,
                                    name=stock_name.strip() or symbol,
                                    quantity=int(quantity),
                                    avg_cost=float(avg_cost),
                                    notes=notes,
                                )
                                st.success(f"{symbol} 已加入“{portfolio.name}”")
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))

                    with st.expander("✏️ 编辑组合信息"):
                        with st.form(f"edit_portfolio_{portfolio.id}"):
                            edit_name = st.text_input(
                                "组合名称", value=portfolio.name, max_chars=100
                            )
                            edit_description = st.text_area(
                                "组合描述",
                                value=portfolio.description,
                                max_chars=500,
                            )
                            edit_submitted = st.form_submit_button(
                                "保存修改", use_container_width=True
                            )
                        if edit_submitted:
                            try:
                                watchlist_manager.update_portfolio(
                                    portfolio.id,
                                    name=edit_name,
                                    description=edit_description,
                                )
                                st.success("组合信息已更新")
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))

                    if portfolio.stocks:
                        with st.expander("➖ 移除股票"):
                            stock_options = {
                                f"{stock.symbol} {stock.name}": stock.symbol
                                for stock in portfolio.stocks
                            }
                            selected_label = st.selectbox(
                                "选择要移除的股票",
                                list(stock_options),
                                key=f"remove_symbol_{portfolio.id}",
                            )
                            confirm_remove = st.checkbox(
                                "我确认从当前组合移除该股票",
                                key=f"confirm_remove_stock_{portfolio.id}",
                            )
                            if st.button(
                                "移除股票",
                                disabled=not confirm_remove,
                                key=f"remove_stock_{portfolio.id}",
                                use_container_width=True,
                            ):
                                watchlist_manager.remove_stock(
                                    portfolio.id,
                                    stock_options[selected_label],
                                )
                                st.rerun()

                    # 操作按钮行
                    btn_col1, btn_col2, btn_col3 = st.columns([2, 1, 1])
                    with btn_col1:
                        nav_to_page(
                            "market",
                            "前往选股",
                            icon="📡",
                            key_suffix=f"{getattr(portfolio, 'id', idx)}_{idx}",
                        )
                    with btn_col2:
                        if st.button(
                            "🗄️ 归档",
                            key=f"archive_{portfolio.id}",
                            use_container_width=True,
                            help="归档后可在“归档与回收站”恢复",
                        ):
                            watchlist_manager.archive_portfolio(portfolio.id)
                            st.rerun()
                    with btn_col3:
                        # 二次确认删除
                        confirm_key = f"confirm_del_{portfolio.id}"
                        if st.session_state.get(confirm_key, False):
                            if st.button(
                                "⚠️ 移入回收站",
                                key=f"do_del_{portfolio.id}",
                                type="primary",
                                use_container_width=True,
                            ):
                                watchlist_manager.delete_portfolio(portfolio.id)
                                st.session_state[confirm_key] = False
                                st.rerun()
                        else:
                            if st.button(
                                "🗑️ 删除",
                                key=f"del_port_{portfolio.id}",
                                use_container_width=True,
                            ):
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
            description = st.text_area(
                "📝 组合描述", placeholder="简要描述组合的投资策略和目标...", height=100
            )
            submitted = st.form_submit_button(
                "✨ 创建组合", type="primary", use_container_width=True
            )

            if submitted:
                try:
                    created = watchlist_manager.create_portfolio(name, description)
                    st.success(f"✅ 组合 '{created.name}' 创建成功！")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

    with tab3:
        archived = watchlist_manager.list_by_state("archived")
        deleted = watchlist_manager.list_by_state("deleted")

        st.subheader("已归档")
        if archived:
            for portfolio in archived:
                col_name, col_action = st.columns([4, 1])
                col_name.write(f"📦 {portfolio.name} · {len(portfolio.stocks)} 只股票")
                if col_action.button(
                    "恢复",
                    key=f"restore_archived_{portfolio.id}",
                    use_container_width=True,
                ):
                    watchlist_manager.restore_portfolio(portfolio.id)
                    st.rerun()
        else:
            st.caption("暂无已归档组合")

        st.subheader("回收站")
        st.caption("删除操作可恢复；当前不提供不可逆的页面内永久删除。")
        if deleted:
            for portfolio in deleted:
                col_name, col_action = st.columns([4, 1])
                col_name.write(f"🗑️ {portfolio.name} · {len(portfolio.stocks)} 只股票")
                if col_action.button(
                    "恢复",
                    key=f"restore_deleted_{portfolio.id}",
                    use_container_width=True,
                ):
                    watchlist_manager.restore_portfolio(portfolio.id)
                    st.rerun()
        else:
            st.caption("回收站为空")

    # 底部导航
    st.divider()
    st.caption("📌 下一步")
    c1, c2, c3 = st.columns(3)
    with c1:
        nav_to_page("market", "前往市场选股", icon="📡")
    with c2:
        nav_to_page("alerts", "创建价格预警", icon="🔔")
    with c3:
        nav_to_page("backtest", "验证回测策略", icon="📊")
