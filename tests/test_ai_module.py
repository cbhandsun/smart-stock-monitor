"""
tests/test_ai_module.py — AI 模块测试（使用 mock）
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCallAiForStockDiagnosis:
    """测试 AI 诊断函数"""

    @patch('ai_module.client')
    def test_successful_response(self, mock_client):
        """测试正常 AI 响应"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "# 诊断报告\n看多"
        mock_client.chat.completions.create.return_value = mock_response

        from core.ai_client import call_ai_for_stock_diagnosis
        result = call_ai_for_stock_diagnosis("601318", "中国平安", pd.DataFrame(), "看多信号")

        assert isinstance(result, str)
        assert "诊断报告" in result

    @patch('ai_module.client')
    def test_api_error_returns_error_message(self, mock_client):
        """测试 API 错误时返回错误信息"""
        mock_client.chat.completions.create.side_effect = Exception("API rate limit")

        from core.ai_client import call_ai_for_stock_diagnosis
        result = call_ai_for_stock_diagnosis("601318", "中国平安", pd.DataFrame(), "")

        assert "⚠️" in result or "失败" in result

    @patch('ai_module.client')
    def test_with_reports_df(self, mock_client):
        """测试传入研报数据时使用正确的 prompt"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "分析结果"
        mock_client.chat.completions.create.return_value = mock_response

        reports = pd.DataFrame({"标题": ["研报1"], "评级": ["买入"]})
        from core.ai_client import call_ai_for_stock_diagnosis
        result = call_ai_for_stock_diagnosis("601318", "中国平安", reports, "金叉信号")

        # 验证 API 被调用
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        prompt_content = call_args.kwargs['messages'][1]['content']
        assert "601318" in prompt_content
        assert "中国平安" in prompt_content

    @patch('ai_module.client')
    def test_empty_reports(self, mock_client):
        """测试空研报时 prompt 包含'暂无'"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "结果"
        mock_client.chat.completions.create.return_value = mock_response

        from core.ai_client import call_ai_for_stock_diagnosis
        call_ai_for_stock_diagnosis("000001", "平安银行", pd.DataFrame(), "")

        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args.kwargs['messages'][1]['content']
        assert "暂无" in prompt
