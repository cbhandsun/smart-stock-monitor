"""
📚 研报中心页面
"""
import streamlit as st
from modules.research.research_center import ResearchCenter

research_center = ResearchCenter()


from components.dna_analyzer import render_dna_analyzer

def render(L, my_stocks, name_map):
    from components.ui_components import page_header
    page_header("研报中心", icon="📚")

    tab1, tab2, tab3 = st.tabs(["个股研报", "最新研报", "搜索研报"])

    with tab1:
        symbol = st.text_input("股票代码", value=st.session_state['selected_stock'], key="research_symbol")
        if symbol:
            reports = research_center.get_stock_reports(symbol, limit=20)
            if not reports.empty:
                st.dataframe(reports, use_container_width=True)
                rating_dist = research_center.get_rating_distribution(symbol)
                if rating_dist:
                    st.json(rating_dist)
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

    # Global DNA Analyzer Injection
    render_dna_analyzer(L, my_stocks, name_map)
