"""
tests/test_backtest.py — 回测引擎逻辑测试
"""
import pytest
import pandas as pd
import numpy as np
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.backtest.backtest_engine import BacktestEngine, StrategyTemplate
from unittest.mock import patch

@pytest.fixture(autouse=True)
def mock_fetch_kline():
    """Mock fetch_kline to return empty DataFrame to keep unit testing offline and fast"""
    with patch('modules.data_loader.fetch_kline', return_value=pd.DataFrame()):
        yield


def test_backtest_engine_run():
    # 构造模拟 K 线数据，长度为 30 天
    dates = pd.date_range(start='2026-01-01', periods=30)
    # 制造一个价格上升和下降的趋势，以便触发交叉信号
    prices = [10.0 + i * 0.5 if i < 15 else 17.5 - (i - 15) * 0.5 for i in range(30)]
    
    kline_df = pd.DataFrame({
        '日期': dates,
        '开盘': prices,
        '最高': [p + 0.2 for p in prices],
        '最低': [p - 0.2 for p in prices],
        '收盘': prices,
        '成交量': [1000 + i * 10 for i in range(30)],
        '成交额': [10000 + i * 100 for i in range(30)]
    })
    
    engine = BacktestEngine(initial_cash=100000.0, commission_rate=0.0003)
    engine.set_strategy(*StrategyTemplate.ma_cross_strategy(5, 10))
    
    data_dict = {'601933': kline_df}
    result = engine.run(data_dict, '2026-01-01', '2026-01-30')
    
    assert result is not None
    assert 'initial_cash' in result
    assert result['initial_cash'] == 100000.0
    assert 'daily_values' in result
    assert len(result['daily_values']) > 0
    assert 'trades_list' in result
    
    # 验证交易记录结构
    trades_list = result['trades_list']
    if trades_list:
        first_trade = trades_list[0]
        assert 'entry_date' in first_trade
        assert 'exit_date' in first_trade
        assert 'size' in first_trade
        assert 'entry_price' in first_trade
        assert 'exit_price' in first_trade
        assert 'pnl' in first_trade
        assert 'return_pct' in first_trade
        assert 'direction' in first_trade
        assert first_trade['direction'] in ['做多', '做空']


def test_backtest_engine_run_multi_asset():
    # 构造模拟 K 线数据，长度为 30 天
    dates = pd.date_range(start='2026-01-01', periods=30)
    prices1 = [10.0 + i * 0.5 if i < 15 else 17.5 - (i - 15) * 0.5 for i in range(30)]
    prices2 = [8.0 + i * 0.3 for i in range(30)]
    
    kline1 = pd.DataFrame({'日期': dates, '收盘': prices1, '成交量': 1000, '成交额': 10000})
    kline2 = pd.DataFrame({'日期': dates, '收盘': prices2, '成交量': 2000, '成交额': 20000})
    
    engine = BacktestEngine(initial_cash=100000.0, commission_rate=0.0003)
    engine.set_strategy(*StrategyTemplate.ma_cross_strategy(5, 10))
    
    data_dict = {'601318': kline1, '000001': kline2}
    result = engine.run(data_dict, '2026-01-01', '2026-01-30')
    
    assert result is not None
    assert 'initial_cash' in result
    assert result['initial_cash'] == 100000.0
    assert 'alpha' in result
    assert 'beta' in result
    assert 'sortino_ratio' in result
    assert 'info_ratio' in result
    
    if result['trades_list']:
        for trade in result['trades_list']:
            assert 'symbol' in trade
            assert trade['symbol'] in ['601318', '000001']
