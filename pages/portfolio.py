"""
📁 组合管理页面
"""
import streamlit as st
import pandas as pd
from modules.portfolio.watchlist_manager import WatchlistManager

watchlist_manager = WatchlistManager()


def render(L):
    st.header("📁 组合管理")

    tab1, tab2 = st.tabs(["我的组合", "创建组合"])

    with tab1:
        portfolios = watchlist_manager.list_portfolios()
        if portfolios:
            for portfolio in portfolios:
                with st.expander(f"📂 {portfolio.name} ({len(portfolio.stocks)} 只股票)"):
                    st.write(f"描述: {portfolio.description}")
                    st.write(f"创建时间: {portfolio.created_at}")

                    if portfolio.stocks:
                        stock_data = []
                        for s in portfolio.stocks:
                            stock_data.append({
                                "代码": s.symbol, "名称": s.name,
                                "数量": s.quantity, "成本": s.avg_cost,
                                "标签": ", ".join(s.tags) if s.tags else "-",
                                "备注": s.notes or "-"
                            })
                        st.dataframe(pd.DataFrame(stock_data), use_container_width=True)

                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("删除组合", key=f"del_port_{portfolio.id}"):
                            watchlist_manager.delete_portfolio(portfolio.id)
                            st.rerun()
        else:
            st.info("暂无组合，请创建新组合")

    with tab2:
        with st.form("create_portfolio"):
            name = st.text_input("组合名称")
            description = st.text_area("组合描述")
            submitted = st.form_submit_button("创建组合", type="primary")

            if submitted and name:
                watchlist_manager.create_portfolio(name, description)
                st.success(f"组合 '{name}' 创建成功！")
                st.rerun()
