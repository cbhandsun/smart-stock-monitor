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
    from components.ui_components import page_header, stock_selector
    page_header("智能研报分析", icon="📖")

    symbol = stock_selector(key_suffix="research_analyzer")
    stock_name = name_map.get(symbol, symbol)

    if symbol:
        # 检查是否切换了股票，切换后清空问答历史
        if "last_rag_symbol" not in st.session_state or st.session_state["last_rag_symbol"] != symbol:
            st.session_state["rag_chat_history"] = []
            st.session_state["last_rag_symbol"] = symbol

        # 获取真实研报
        reports_df = fetch_research_reports(symbol)

        tab1, tab2, tab3, tab4 = st.tabs(["研报分析", "多研报对比", "评级趋势", "研报智能问答 (RAG)"])

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
                st.caption("💡 智能提取该股的最新核心评级、目标价、投资要点及潜在风险因素。")
                if st.button("生成智能摘要", type="primary", help="点击调用大模型综合分析该股票最新一期研报并输出摘要。"):
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
            st.caption("💡 汇总并对比多篇研报观点，展示券商共识评级、平均目标价及核心分歧。")
            if reports_df.empty:
                st.info("暂无研报可供对比，请等待数据更新")
            elif st.button("开始对比分析", type="primary", help="点击对比已抓取的多篇机构研报，自动识别并提炼核心共识与分歧点。"):
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
            st.caption("💡 聚合统计各大机构的历史投资评级分布，辅助判断市场对该股的共识方向。")
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

        with tab4:
            st.subheader("研报 AI 智能问答 (RAG)")
            if reports_df.empty:
                st.info("暂无研报数据，无法使用问答功能")
            else:
                st.html('''<div class="ssm-card" style="margin-bottom:15px; border-left:4px solid #6366f1;">
                    <div class="ssm-card-title" style="color:#a5b4fc; font-weight:600; font-size:0.92rem; display:flex; align-items:center; gap:6px;">
                        💡 智能研报检索问答助手指南
                    </div>
                    <div style="font-size:0.82rem; color:#cbd5e1; margin-top:6px; line-height:1.45;">
                        <strong>检索增强生成 (RAG) 机制：</strong> 系统会对当前标的的历史研报原文进行智能文本分块（Chunking），并利用高维向量嵌入对您的问题进行语义匹配，自动检索关联度最高的研报上下文段落，最后将匹配文本交由大语言模型（LLM）进行提炼总结。这能极大程度避免“AI 幻觉”，确保回答有据可依。<br/>
                        <strong style="color:#818cf8; display:block; margin-top:8px;">推荐提问示例（可复制作为参考）：</strong>
                        <ul style="margin-top:4px; padding-left:18px; margin-bottom:0;">
                            <li><code>这只股票核心投资亮点和增长驱动力是什么？</code></li>
                            <li><code>各家券商研报中达成了哪些共识？有哪些核心分歧点？</code></li>
                            <li><code>研报里提及了该公司的哪些潜在风险提示？</code></li>
                            <li><code>公司近期的财务表现、营收预测与估值水平如何？</code></li>
                        </ul>
                    </div>
                </div>''')
                
                # 展现对话历史
                if "rag_chat_history" not in st.session_state:
                    st.session_state["rag_chat_history"] = []
                
                for item in st.session_state["rag_chat_history"]:
                    with st.chat_message(item["role"]):
                        st.markdown(item["content"])
                
                # 输入问题
                query = st.chat_input("询问研报问题，例如：“这只股票有哪些核心增长点？”")
                if query:
                    with st.chat_message("user"):
                        st.markdown(query)
                    
                    st.session_state["rag_chat_history"].append({"role": "user", "content": query})
                    
                    with st.chat_message("assistant"):
                        with st.spinner("检索研报并生成回答中..."):
                            response = research_analyzer.answer_query_with_rag(query, symbol, stock_name, reports_df)
                            st.markdown(response)
                    
                    st.session_state["rag_chat_history"].append({"role": "assistant", "content": response})
