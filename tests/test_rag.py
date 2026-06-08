"""
tests/test_rag.py — 研报智能问答 RAG 功能测试
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.ai.research_analyzer import ResearchAnalyzer


def test_answer_query_with_rag_empty_reports():
    analyzer = ResearchAnalyzer()
    df = pd.DataFrame()
    res = analyzer.answer_query_with_rag("核心增长点是什么？", "601933", "永辉超市", df)
    assert "暂无近期研报" in res


def test_answer_query_with_rag_successful_retrieval():
    # 模拟 AI 模块，避免发起真实网络请求
    mock_ai = MagicMock()
    mock_ai.generate_response.return_value = "Mocked RAG response based on reports."
    
    analyzer = ResearchAnalyzer(ai_manager=mock_ai)
    
    # 构造假研报数据
    data = {
        '研报名称': ['永辉超市2026年报分析', '零售行业季度研究报告'],
        '机构': ['招商证券', '中信证券'],
        '作者': ['张三', '李四'],
        '摘要': [
            '永辉超市近期大力推广线上配送业务，线上GMV同比增长35%，成为核心的业绩增长驱动力。',
            '整个零售行业线下客流有所恢复，但线上数字化转型依然是各大商超的主要竞争点。'
        ]
    }
    df = pd.DataFrame(data)
    
    # 执行 RAG 问答
    query = "永辉超市的核心增长驱动力是什么？"
    res = analyzer.answer_query_with_rag(query, "601933", "永辉超市", df)
    
    # 校验 AI 的生成调用
    assert mock_ai.generate_response.called
    args, kwargs = mock_ai.generate_response.call_args
    prompt = args[0]
    
    # 验证检索器成功找到了最相关的“线上配送业务” Chunk，并包含在 Prompt 里
    assert "线上GMV同比增长35%" in prompt
    assert "永辉超市近期大力推广线上配送业务" in prompt
    # 验证返回值
    assert res == "Mocked RAG response based on reports."
