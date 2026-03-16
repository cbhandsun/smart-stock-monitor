"""
tests/test_quant.py — 量化指标计算测试
"""
import pytest
import pandas as pd
import numpy as np

# 直接导入被测模块（不依赖 akshare/streamlit）
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.quant import calculate_metrics, calculate_all_indicators


class TestCalculateMetrics:
    """测试 calculate_metrics 函数"""

    def test_returns_dict_with_expected_keys(self, sample_kline_df):
        result = calculate_metrics(sample_kline_df)
        expected_keys = [
            'volatility_ann', 'max_drawdown', 'rsi',
            'macd', 'macd_signal', 'macd_hist',
            'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_percent',
            'kdj_k', 'kdj_d', 'kdj_j',
            'cci', 'obv', 'obv_ma',
            'dmi_plus_di', 'dmi_minus_di', 'dmi_adx',
        ]
        for key in expected_keys:
            assert key in result, f"缺少指标: {key}"

    def test_empty_df_returns_empty_dict(self, empty_df):
        assert calculate_metrics(empty_df) == {}

    def test_rsi_in_valid_range(self, sample_kline_df):
        result = calculate_metrics(sample_kline_df)
        assert 0 <= result['rsi'] <= 100, f"RSI 超出范围: {result['rsi']}"

    def test_max_drawdown_is_negative(self, sample_kline_df):
        result = calculate_metrics(sample_kline_df)
        assert result['max_drawdown'] <= 0, "最大回撤应为负值或零"

    def test_volatility_is_positive(self, sample_kline_df):
        result = calculate_metrics(sample_kline_df)
        assert result['volatility_ann'] >= 0, "年化波动率应非负"

    def test_bollinger_band_order(self, sample_kline_df):
        result = calculate_metrics(sample_kline_df)
        assert result['bb_upper'] >= result['bb_middle'] >= result['bb_lower'], \
            "布林带应满足 上轨 >= 中轨 >= 下轨"


class TestCalculateAllIndicators:
    """测试 calculate_all_indicators 函数"""

    def test_adds_indicator_columns(self, sample_kline_df):
        result = calculate_all_indicators(sample_kline_df)
        expected_cols = ['RSI', 'MACD', 'MACD_Signal', 'MACD_Hist',
                         'BB_Upper', 'BB_Middle', 'BB_Lower',
                         'KDJ_K', 'KDJ_D', 'KDJ_J', 'CCI', 'OBV']
        for col in expected_cols:
            assert col in result.columns, f"缺少列: {col}"

    def test_empty_df_returns_empty(self, empty_df):
        result = calculate_all_indicators(empty_df)
        assert result.empty

    def test_does_not_modify_original(self, sample_kline_df):
        original_cols = list(sample_kline_df.columns)
        calculate_all_indicators(sample_kline_df)
        assert list(sample_kline_df.columns) == original_cols, "不应修改原始DataFrame"

    def test_preserves_row_count(self, sample_kline_df):
        result = calculate_all_indicators(sample_kline_df)
        assert len(result) == len(sample_kline_df), "行数应保持一致"

    def test_rsi_column_values_valid(self, sample_kline_df):
        result = calculate_all_indicators(sample_kline_df)
        rsi_valid = result['RSI'].dropna()
        assert (rsi_valid >= 0).all() and (rsi_valid <= 100).all(), "RSI列应在0-100范围"
