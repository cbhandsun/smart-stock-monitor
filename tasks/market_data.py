from celery import shared_task
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cache import RedisCache
from modules.portfolio.watchlist_manager import WatchlistManager

@shared_task(bind=True, max_retries=3)
def update_stock_quote(self, symbol: str):
    """更新单个股票行情"""
    try:
        from modules.data_loader import fetch_kline
        
        cache = RedisCache()
        data = fetch_kline(symbol)
        
        if not data.empty:
            cache.set_stock_data(symbol, data.to_dict(), "kline", expire=300)
            return f"Updated {symbol}"
        else:
            return f"No data for {symbol}"
            
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)

@shared_task
def update_all_stocks():
    """更新所有自选股行情"""
    try:
        manager = WatchlistManager()
        portfolios = manager.list_portfolios()
        
        symbols = set()
        for portfolio in portfolios:
            for stock in portfolio.stocks:
                symbols.add(stock.symbol)
        
        # 如果没有组合，使用默认列表
        if not symbols:
            symbols = {'601318', '000001', '600519'}
        
        # 发送异步任务
        for symbol in symbols:
            update_stock_quote.delay(symbol)
        
        return f"Queued updates for {len(symbols)} stocks"
        
    except Exception as e:
        return f"Error: {str(e)}"

@shared_task
def update_market_overview():
    """更新市场概览"""
    try:
        from main import get_market_overview
        from core.cache import RedisCache
        
        cache = RedisCache()
        data = get_market_overview()
        
        if not data.empty:
            cache.set_market_overview(data.to_dict(), expire=60)
            return "Market overview updated"
        
        return "No market data"
        
    except Exception as e:
        return f"Error: {str(e)}"
