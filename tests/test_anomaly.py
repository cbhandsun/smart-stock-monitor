"""
tests/test_anomaly.py — 异常检测器测试
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.ai.anomaly_detector import (
    AnomalyDetector, AnomalyType, AlertLevel, AnomalyEvent
)


class TestDetectPriceGap:
    """测试价格跳空检测"""

    def test_gap_up_detected(self):
        detector = AnomalyDetector()
        data = pd.Series({'open': 110.0, 'close': 112.0})
        event = detector.detect_price_gap("601318", data, prev_close=100.0)
        assert event is not None
        assert event.anomaly_type == AnomalyType.PRICE_GAP_UP
        assert event.metrics['gap_pct'] == pytest.approx(0.1, rel=0.01)

    def test_gap_down_detected(self):
        detector = AnomalyDetector()
        data = pd.Series({'open': 90.0, 'close': 88.0})
        event = detector.detect_price_gap("601318", data, prev_close=100.0)
        assert event is not None
        assert event.anomaly_type == AnomalyType.PRICE_GAP_DOWN

    def test_no_gap(self):
        detector = AnomalyDetector()
        data = pd.Series({'open': 100.5, 'close': 101.0})
        event = detector.detect_price_gap("601318", data, prev_close=100.0)
        assert event is None

    def test_zero_prev_close_returns_none(self):
        detector = AnomalyDetector()
        data = pd.Series({'open': 100.0})
        assert detector.detect_price_gap("601318", data, prev_close=0) is None

    def test_large_gap_up_is_warning(self):
        detector = AnomalyDetector()
        data = pd.Series({'open': 106.0})
        event = detector.detect_price_gap("601318", data, prev_close=100.0)
        assert event.level == AlertLevel.WARNING


class TestDetectVolumeSpike:
    """测试成交量激增检测"""

    def test_no_spike_with_insufficient_history(self):
        detector = AnomalyDetector()
        event = detector.detect_volume_spike("601318", 1000000)
        assert event is None  # 历史不够，不触发

    def test_spike_detected(self):
        detector = AnomalyDetector()
        # 填充20天正常历史
        for _ in range(25):
            detector.volume_history["601318"].append(100000)
        event = detector.detect_volume_spike("601318", 500000)
        assert event is not None
        assert event.anomaly_type == AnomalyType.VOLUME_SPIKE

    def test_normal_volume_no_event(self):
        detector = AnomalyDetector()
        for _ in range(25):
            detector.volume_history["601318"].append(100000)
        event = detector.detect_volume_spike("601318", 120000)
        assert event is None


class TestDetectBreakout:
    """测试价格突破检测"""

    def test_breakout_up(self, sample_kline_df):
        detector = AnomalyDetector()
        high_price = sample_kline_df['最高'].max() * 1.1
        event = detector.detect_breakout("601318", high_price, sample_kline_df, window=20)
        assert event is not None
        assert event.anomaly_type == AnomalyType.PRICE_BREAKOUT

    def test_breakdown(self, sample_kline_df):
        detector = AnomalyDetector()
        low_price = sample_kline_df['最低'].min() * 0.85
        event = detector.detect_breakout("601318", low_price, sample_kline_df, window=20)
        assert event is not None
        assert event.anomaly_type == AnomalyType.PRICE_BREAKDOWN

    def test_normal_price_no_event(self, sample_kline_df):
        detector = AnomalyDetector()
        mid_price = sample_kline_df['收盘'].median()
        event = detector.detect_breakout("601318", mid_price, sample_kline_df, window=20)
        assert event is None

    def test_insufficient_data(self, small_df):
        detector = AnomalyDetector()
        event = detector.detect_breakout("601318", 100.0, small_df, window=20)
        assert event is None


class TestDetectBlockTrade:
    """测试大宗交易检测"""

    def test_block_trade_discount(self):
        detector = AnomalyDetector()
        event = detector.detect_block_trade("601318", {
            'amount': 5000000, 'volume': 100000,
            'price': 90.0, 'market_price': 100.0
        })
        assert event is not None
        assert "折价" in event.description

    def test_below_threshold_no_event(self):
        detector = AnomalyDetector()
        event = detector.detect_block_trade("601318", {
            'amount': 100000, 'volume': 1000, 'price': 100.0
        })
        assert event is None


class TestAnalyze:
    """测试综合分析"""

    def test_analyze_returns_list(self, sample_kline_df):
        detector = AnomalyDetector()
        data = {
            'open': 110.0, 'close': 112.0,
            'volume': 500000, 'prev_close': 100.0
        }
        results = detector.analyze("601318", data, sample_kline_df)
        assert isinstance(results, list)

    def test_anomaly_stats_empty_history(self):
        detector = AnomalyDetector()
        stats = detector.get_anomaly_stats("601318")
        assert stats['total_count'] == 0
        assert stats['avg_confidence'] == 0


class TestDetectRapidChange:
    """测试快速变动检测"""

    def test_rapid_rise_detected(self):
        detector = AnomalyDetector()
        event = detector.detect_rapid_change("601318", [0.03, 0.04])
        assert event is not None
        assert "上涨" in event.description

    def test_rapid_drop_detected(self):
        detector = AnomalyDetector()
        event = detector.detect_rapid_change("601318", [-0.03, -0.04])
        assert event is not None
        assert "下跌" in event.description

    def test_small_change_no_event(self):
        detector = AnomalyDetector()
        event = detector.detect_rapid_change("601318", [0.01, 0.01])
        assert event is None
