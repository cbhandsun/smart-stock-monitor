"""
📖 智能研报分析页面
Mock data replaced → 使用 fetch_research_reports 获取真实研报
"""
import streamlit as st
import pandas as pd
from modules.data_loader import fetch_research_reports
from modules.ai.research_analyzer import ResearchAnalyzer, ResearchReport
from utils.export import render_export_panel

research_analyzer = ResearchAnalyzer()


def _df_to_research_reports(reports_df: pd.DataFrame, symbol: str, name: str) -> list:
    """将 fetch_research_reports 返回的 DataFrame 转为 ResearchReport 列表"""
    reports = []
    for idx, row in reports_df.iterrows():
        reports.append({
            'id': f'RPT_{symbol}_{idx:03d}',
            'title': str(row.get('研报名称', row.get('title', f'{symbol}研报'))),
            'stock_symbol': symbol,
            'stock_name': name,
            'author': str(row.get('作者', row.get('author', '分析师'))),
            'institution': str(row.get('机构', row.get('institution', '—'))),
            'publish_date': pd.Timestamp(row.get('日期', row.get('date', pd.Timestamp.now()))),
            'content': str(row.get('摘要', row.get('content', '')))
        })
    return reports


def _df_to_compare_reports(reports_df: pd.DataFrame, symbol: str, name: str) -> list:
    """将 DataFrame 转为可对比的 ResearchReport 对象列表"""
    reports = []
    for idx, row in reports_df.iterrows():
        rating = str(row.get('最新评级', row.get('rating', '增持')))
        target_str = str(row.get('目标价', row.get('target_price', '0')))
        try:
            target_price = float(target_str)
        except (ValueError, TypeError):
            target_price = 0.0

        reports.append(ResearchReport(
            id=f'RPT_{idx}',
            title=str(row.get('研报名称', row.get('title', f'研报{idx}'))),
            stock_symbol=symbol,
            stock_name=name,
            author=str(row.get('作者', row.get('author', f'分析师{idx}'))),
            institution=str(row.get('机构', row.get('institution', f'券商{idx}'))),
            publish_date=pd.Timestamp(row.get('日期', pd.Timestamp.now())),
            rating=rating,
            target_price=target_price if target_price > 0 else None,
            current_price=None,
            investment_points=[str(row.get('摘要', ''))[:50]] if row.get('摘要') else [],
            risk_warnings=['市场风险', '政策风险']
        ))
    return reports


def render(L, name_map):
    from components.ui_components import page_header
    page_header("智能研报分析", icon="📖")

    symbol = st.text_input("股票代码", value=st.session_state['selected_stock'], key="research_analyzer_symbol")
    stock_name = name_map.get(symbol, symbol)

    if symbol:
        # 获取真实研报
        reports_df = fetch_research_reports(symbol)

        tab1, tab2, tab3 = st.tabs(["研报分析", "多研报对比", "评级趋势"])

        with tab1:
            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("研报列表")
                if not reports_df.empty:
                    st.dataframe(reports_df, use_container_width=True)
                    render_export_panel(df=reports_df, symbol=symbol, key_prefix="research_list")
                else:
                    st.info("暂无研报数据")

            with col2:
                st.subheader("AI研报摘要")
                if st.button("生成智能摘要", type="primary"):
                    with st.spinner("AI分析中..."):
                        if not reports_df.empty:
                            real_reports = _df_to_research_reports(reports_df, symbol, stock_name)
                        else:
                            # 无真实数据时用占位信息，明确标注
                            real_reports = [{
                                'id': f'RPT_{symbol}_placeholder',
                                'title': f'{stock_name}({symbol}) 综合分析',
                                'stock_symbol': symbol,
                                'stock_name': stock_name,
                                'author': '系统', 'institution': '—',
                                'publish_date': pd.Timestamp.now(),
                                'content': f'暂无真实研报，AI将基于公开信息分析 {stock_name}。'
                            }]

                        analyzed_reports = research_analyzer.batch_analyze(real_reports)
                        if analyzed_reports:
                            report = analyzed_reports[0]
                            st.write(f"**评级**: {report.rating or '未评级'}")
                            st.write(f"**目标价**: {report.target_price or '未给出'}")
                            st.write("**摘要**:")
                            st.write(report.summary or "暂无摘要")
                            if report.investment_points:
                                st.write("**投资要点**:")
                                for point in report.investment_points:
                                    st.write(f"- {point}")
                            if report.risk_warnings:
                                st.write("**风险提示**:")
                                for risk in report.risk_warnings:
                                    st.write(f"- {risk}")

        with tab2:
            st.subheader("多研报对比分析")
            if reports_df.empty:
                st.info("暂无研报可供对比，请等待数据更新")
            elif st.button("开始对比分析", type="primary"):
                real_compare = _df_to_compare_reports(reports_df, symbol, stock_name)
                if len(real_compare) < 2:
                    st.warning("对比分析需要至少 2 篇研报")
                else:
                    comparison = research_analyzer.compare_reports(real_compare)
                    if comparison:
                        col1, col2, col3, col4 = st.columns(4)
                        col1.metric("分析研报数", comparison.reports_analyzed)
                        col2.metric("共识评级", comparison.consensus_rating)
                        col3.metric("评级一致性", f"{comparison.rating_consistency * 100:.0f}%")
                        col4.metric("综合置信度", f"{comparison.confidence_score:.0f}/100")

                        if comparison.avg_target_price:
                            st.write(f"**平均目标价**: {comparison.avg_target_price:.2f}元")
                            st.write(f"**上涨空间**: {comparison.price_upside:+.2f}%")

                        st.write("**共识投资要点**:")
                        for point in comparison.common_points:
                            st.write(f"- {point}")

                        if comparison.divergent_points:
                            st.write("**观点分歧**:")
                            for point in comparison.divergent_points:
                                st.warning(point)

        with tab3:
            st.subheader("评级趋势")
            if not reports_df.empty:
                rating_col = None
                for col_name in ['最新评级', 'rating', '评级']:
                    if col_name in reports_df.columns:
                        rating_col = col_name
                        break

                if rating_col:
                    st.write("**各研报评级分布**:")
                    rating_counts = reports_df[rating_col].value_counts()
                    for rating_val, count in rating_counts.items():
                        st.write(f"- {rating_val}: {count} 篇")
                else:
                    st.info("研报数据中无评级列")
            else:
                st.info("暂无研报数据用于评级趋势分析")
