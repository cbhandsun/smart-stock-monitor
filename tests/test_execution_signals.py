import sys
import os
import pandas as pd

# Add root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.data_loader import calculate_advanced_trading_signals, fetch_trading_signals
from core.recommender import run_recommendation_engine


def test_calculate_advanced_trading_signals():
    print("Testing calculate_advanced_trading_signals for 600519...")
    res = calculate_advanced_trading_signals("sh600519")
    
    assert isinstance(res, dict), "Result must be a dictionary"
    
    required_keys = ["signal", "buy_zone", "stop_loss", "take_profit", "rsi", "macro_trend"]
    for key in required_keys:
        assert key in res, f"Key '{key}' is missing from the result"
        
    print("Fetched execution signal:", res["signal"])
    print("Optimal buy zone:", res["buy_zone"])
    print("Stop loss:", res["stop_loss"])
    print("Take profit:", res["take_profit"])
    print("RSI-14:", res["rsi"])
    print("Macro trend direction:", res["macro_trend"])
    
    assert 0 <= res["rsi"] <= 100, "RSI must be between 0 and 100"
    assert res["macro_trend"] in ["多头", "空头", "未知"], "Invalid macro trend direction"
    print("calculate_advanced_trading_signals passed!")


def test_fetch_trading_signals_wrapper():
    print("Testing fetch_trading_signals string output for 600519...")
    desc = fetch_trading_signals("sh600519")
    assert isinstance(desc, str), "Result must be a string"
    assert len(desc) > 10, "Description string is too short"
    print("Output string description:")
    print(f"  '{desc}'")
    assert "大趋势" in desc or "RSI" in desc, "Output description missing key terms"
    print("fetch_trading_signals wrapper passed!")


def test_recommender_integration():
    print("Testing recommender engine execution fields...")
    res = run_recommendation_engine(top_n=3)
    assert "stocks" in res, "Recommender output missing stocks key"
    
    df_stocks = res["stocks"]
    assert isinstance(df_stocks, pd.DataFrame), "Stocks must be a DataFrame"
    
    if not df_stocks.empty:
        required_cols = ["交易信号", "买入区间", "止损点", "止盈点"]
        for col in required_cols:
            assert col in df_stocks.columns, f"Column '{col}' is missing from recommender output DataFrame"
            
        print("Recommender sample columns:")
        print(df_stocks[["代码", "名称", "总评分", "交易信号", "买入区间", "止损点", "止盈点"]].head(2))
    else:
        print("Recommended stock pool is empty (outside trading hours), skipping detail asserts.")
        
    print("recommender_integration passed!")


if __name__ == "__main__":
    print("Running execution signals tests...")
    test_calculate_advanced_trading_signals()
    print("-" * 50)
    test_fetch_trading_signals_wrapper()
    print("-" * 50)
    test_recommender_integration()
    print("All tests passed successfully!")
