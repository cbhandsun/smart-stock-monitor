import sys
import os
import pandas as pd

# Add root to python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.global_market_data import get_global_realtime_data, get_global_history_data
from modules.us_transmission import calculate_us_transmission_premiums
from modules.sentiment.sentiment_analyzer import get_stock_news, analyze_stock_sentiment
from core.recommender import run_recommendation_engine


def test_global_realtime():
    print("Testing get_global_realtime_data...")
    rt = get_global_realtime_data()
    assert isinstance(rt, dict)
    print("Realtime keys fetched:", list(rt.keys()))
    for k, v in rt.items():
        assert "price" in v
        assert "change_pct" in v
        assert "prev_close" in v
        print(f"  {k}: price={v['price']}, change={v['change_pct']}%")


def test_global_history():
    print("Testing get_global_history_data...")
    hist = get_global_history_data(limit=10)
    assert isinstance(hist, dict)
    print("History keys fetched:", list(hist.keys()))
    for k, df in hist.items():
        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert "date" in df.columns
        assert "close" in df.columns
        assert "change_pct" in df.columns
        print(f"  {k}: shape={df.shape}, last_date={df['date'].iloc[-1]}, last_close={df['close'].iloc[-1]}")


def test_us_transmission():
    print("Testing calculate_us_transmission_premiums...")
    p = calculate_us_transmission_premiums()
    assert isinstance(p, dict)
    assert "sectors" in p
    assert "market_sentiment" in p
    assert "risk_discount" in p
    assert "fx_discount" in p
    print("Risk discount:", p["risk_discount"])
    print("FX discount:", p["fx_discount"])
    print("Market sentiment score:", p["market_sentiment"]["score"])
    print("Market sentiment reason:", p["market_sentiment"]["reason"])
    for sec, details in p["sectors"].items():
        assert "score" in details
        assert "reason" in details
        print(f"  Sector {sec}: score={details['score']}, reason={details['reason']}")


def test_sentiment_analyzer():
    print("Testing sentiment_analyzer...")
    # Test Moutai (600519)
    df_news = get_stock_news("600519")
    assert isinstance(df_news, pd.DataFrame)
    print(f"News fetched for 600519: {len(df_news)} items")
    if not df_news.empty:
        print("First news title:", df_news['新闻标题'].iloc[0])
    
    sent = analyze_stock_sentiment("600519", "贵州茅台")
    assert isinstance(sent, dict)
    assert "sentiment_score" in sent
    assert "sentiment_label" in sent
    assert "is_circuit_break" in sent
    print("Sentiment score for 600519:", sent["sentiment_score"])
    print("Sentiment label for 600519:", sent["sentiment_label"])
    print("Risk circuit break triggered:", sent["is_circuit_break"])
    print("Sentiment reason:", sent["reason"])


def test_recommendation_engine():
    print("Testing run_recommendation_engine...")
    res = run_recommendation_engine(top_n=5)
    assert "stocks" in res
    assert "sectors" in res
    assert "summary" in res
    
    df_stocks = res["stocks"]
    assert isinstance(df_stocks, pd.DataFrame)
    print(f"Stocks recommended count: {len(df_stocks)}")
    if not df_stocks.empty:
        print("Top recommended stocks:")
        print(df_stocks[["排名", "代码", "名称", "总评分", "评级", "舆情分", "美股溢价", "荐股理由"]].head(3))
        # Ensure new fields are present
        assert "舆情分" in df_stocks.columns
        assert "美股溢价" in df_stocks.columns
        assert "全球折价" in df_stocks.columns


if __name__ == "__main__":
    print("Running all tests...")
    test_global_realtime()
    print("-" * 50)
    test_global_history()
    print("-" * 50)
    test_us_transmission()
    print("-" * 50)
    test_sentiment_analyzer()
    print("-" * 50)
    test_recommendation_engine()
    print("All tests passed successfully!")
