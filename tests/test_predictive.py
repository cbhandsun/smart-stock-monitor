"""
tests/test_predictive.py — 预测分析模块测试
"""
import pytest
import pandas as pd
import numpy as np

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.ai.predictive_analysis import PredictiveAnalyzer


@pytest.fixture
def analyzer():
    return PredictiveAnalyzer()


class TestTrendPrediction:
    """测试趋势预测"""

    def test_returns_predictions(self, analyzer, sample_kline_df):
        result = analyzer.trend_prediction(sample_kline_df, days=5)
        assert 'error' not in result
        assert len(result['predictions']) == 5
        assert result['current_price'] > 0
        assert result['confidence'] >= 0

    def test_empty_df_returns_error(self, analyzer, empty_df):
        result = analyzer.trend_prediction(empty_df)
        assert 'error' in result

    def test_insufficient_data(self, analyzer, small_df):
        result = analyzer.trend_prediction(small_df, days=5)
        assert 'error' in result
        assert '数据不足' in result['error']

    def test_different_methods(self, analyzer, sample_kline_df):
        for method in ['linear', 'poly', 'rf']:
            result = analyzer.trend_prediction(sample_kline_df, days=3, method=method)
            # 至少不应报错（如无sklearn则走简单线性）
            assert isinstance(result, dict)

    def test_trend_direction_is_valid(self, analyzer, sample_kline_df):
        result = analyzer.trend_prediction(sample_kline_df, days=5)
        assert result['trend'] in ['up', 'down', 'unknown']


class TestRiskAssessment:
    """测试风险评估"""

    def test_returns_risk_level(self, analyzer, sample_kline_df):
        result = analyzer.risk_assessment(sample_kline_df)
        assert 'error' not in result
        assert result['risk_level'] in ['Low', 'Medium', 'High']
        assert 0 <= result['risk_score'] <= 100

    def test_volatility_is_positive(self, analyzer, sample_kline_df):
        result = analyzer.risk_assessment(sample_kline_df)
        assert result['volatility'] >= 0

    def test_max_drawdown_is_negative(self, analyzer, sample_kline_df):
        result = analyzer.risk_assessment(sample_kline_df)
        assert result['max_drawdown'] <= 0

    def test_insufficient_data(self, analyzer, small_df):
        result = analyzer.risk_assessment(small_df)
        assert 'error' in result


class TestSupportResistance:
    """测试支撑阻力位"""

    def test_returns_levels(self, analyzer, sample_kline_df):
        result = analyzer.support_resistance(sample_kline_df)
        assert 'error' not in result
        assert result['resistance'] >= result['support']
        assert result['current_price'] > 0

    def test_fibonacci_levels(self, analyzer, sample_kline_df):
        result = analyzer.support_resistance(sample_kline_df)
        assert result['fib_382'] >= result['fib_500'] >= result['fib_618']

    def test_position_field(self, analyzer, sample_kline_df):
        result = analyzer.support_resistance(sample_kline_df)
        assert result['position'] in ['above_support', 'below_support']

    def test_insufficient_data(self, analyzer, small_df):
        result = analyzer.support_resistance(small_df, window=20)
        assert 'error' in result


class TestMomentumAnalysis:
    """测试动量分析"""

    def test_returns_returns(self, analyzer, sample_kline_df):
        result = analyzer.momentum_analysis(sample_kline_df)
        assert 'error' not in result
        assert 'returns_1d' in result
        assert 'momentum_score' in result
        assert 0 <= result['momentum_score'] <= 100

    def test_direction_is_valid(self, analyzer, sample_kline_df):
        result = analyzer.momentum_analysis(sample_kline_df)
        valid_dirs = ['Strong Bullish', 'Bullish', 'Neutral', 'Bearish', 'Strong Bearish']
        assert result['momentum_direction'] in valid_dirs

    def test_insufficient_data(self, analyzer, small_df):
        result = analyzer.momentum_analysis(small_df)
        assert 'error' in result
