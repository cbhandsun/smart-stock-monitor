"""
📚 研报中心页面
"""
import streamlit as st
from modules.research.research_center import ResearchCenter
from components.ui_components import page_header, stock_selector, nav_to_page

research_center = ResearchCenter()


def render(L, my_stocks, name_map):
    page_header("研报中心", icon="📚")

    tab1, tab2, tab3 = st.tabs(["个股研报", "最新研报", "搜索研报"])

    with tab1:
        symbol = stock_selector(key_suffix="research")
        if symbol:
            reports = research_center.get_stock_reports(symbol, limit=20)
            if not reports.empty:
                st.dataframe(reports, use_container_width=True)
                rating_dist = research_center.get_rating_distribution(symbol)
                if rating_dist:
                    st.json(rating_dist)

                # 跨页导航
                st.divider()
                st.caption("📌 下一步")
                c1, c2 = st.columns(2)
                with c1:
                    nav_to_page('market', '前往深度分析看盘', icon='📊', stock_code=symbol)
                with c2:
                    nav_to_page('research_analyzer', '用 AI 分析研报', icon='📖', stock_code=symbol)
            else:
                st.info("暂无研报数据")

    with tab2:
        latest = research_center.get_latest_reports(limit=20)
        if not latest.empty:
            st.dataframe(latest, use_container_width=True)
        else:
            st.info("暂无最新研报")

    with tab3:
        keyword = st.text_input("搜索关键词")
        if keyword:
            results = research_center.search_reports(keyword, limit=20)
            if not results.empty:
                st.dataframe(results, use_container_width=True)
            else:
                st.info("未找到相关研报")
