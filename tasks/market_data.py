import sys
import os
import logging
from celery import shared_task
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cache import RedisCache
from modules.portfolio.watchlist_manager import WatchlistManager

@shared_task(bind=True, max_retries=3)
def update_stock_quote(self, symbol: str):
    """更新单个股票行情（带状态报告）"""
    cache = RedisCache()
    status_key = f"status:sync:{symbol}"
    
    try:
        from modules.data_loader import fetch_kline, get_last_timestamp
        
        # 更新状态：同步中
        status_data = {
            "status": "syncing",
            "last_run": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "progress": 0.5
        }
        cache.set(status_key, status_data, expire=86400)
        
        data = fetch_kline(symbol)
        
        if not data.empty:
            cache.set_stock_data(symbol, data.to_dict(), "kline", expire=300)
            
            # 更新状态：成功
            status_data.update({
                "status": "success",
                "count": len(data),
                "last_date": data['日期'].iloc[-1] if '日期' in data else "N/A",
                "progress": 1.0
            })
            cache.set(status_key, status_data, expire=86400)
            return f"Updated {symbol}"
        else:
            status_data.update({"status": "no_data", "progress": 0})
            cache.set(status_key, status_data, expire=86400)
            return f"No data for {symbol}"
            
    except Exception as exc:
        status_data.update({"status": "error", "error": str(exc), "progress": 0})
        cache.set(status_key, status_data, expire=86400)
        raise self.retry(exc=exc, countdown=60)

@shared_task
def sync_historical_data(symbol: str, years: int = 5):
    """同步历史深挖数据 (后台长任务)"""
    cache = RedisCache()
    status_key = f"status:sync_full:{symbol}"
    
    try:
        from modules.data_loader import fetch_kline, merge_kline_data, _save_to_cache, get_last_timestamp
        import datetime
        
        # 初始状态
        status_data = {
            "status": "syncing",
            "start_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "target": f"{years} years"
        }
        cache.set(status_key, status_data, expire=86400)

        from core.tushare_client import get_ts_client
        ts = get_ts_client()
        if not ts.available:
            status_data.update({"status": "error", "error": "Tushare unavailable"})
            cache.set(status_key, status_data, expire=86400)
            return "Tushare unavailable"

        # 执行深挖
        target_date = (datetime.datetime.now() - datetime.timedelta(days=365*years)).strftime("%Y%m%d")
        df = ts.get_daily(symbol, start_date=target_date)
        
        if df is not None and not df.empty:
            df['周期'] = 'daily'
            # 合并到现有缓存 (如果有)
            from modules.data_loader import _load_from_cache
            cached = _load_from_cache(symbol, 'daily', ttl_seconds=3600*24*365)
            full_df = merge_kline_data(cached, df)
            _save_to_cache(full_df, symbol, 'daily')
            
            status_data.update({
                "status": "success", 
                "count": len(full_df),
                "new_added": len(df),
                "end_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            cache.set(status_key, status_data, expire=86400)
            return f"Full sync success for {symbol}: {len(full_df)} total bars"
        
        status_data.update({"status": "no_data"})
        cache.set(status_key, status_data, expire=86400)
        return "No data fetched"
        
    except Exception as e:
        cache.set(status_key, {"status": "error", "error": str(e)}, expire=86400)
        return f"Full sync error: {str(e)}"

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

@shared_task(name='tasks.market_data.prewarm_market_snapshot')
def prewarm_market_snapshot():
    """
    预热全市场快照任务 (后台自动刷选股基础因子)
    """
    try:
        from main import get_full_market_data
        from core.cache import RedisCache
        
        # get_full_market_data 内部逻辑：
        # 1. 尝试 Tushare 快照
        # 2. 尝试 AkShare 实时榜单
        # 3. 结果会自动存入 Redis Cache
        df = get_full_market_data()
        if not df.empty:
            return f"Market snapshot pre-warmed: {len(df)} stocks cached"
        return "Pre-warm failed: empty dataset"
    except Exception as e:
        return f"Pre-warm error: {str(e)}"

@shared_task(name='tasks.market_data.sync_market_valuation')
def sync_market_valuation():
    """
    同步全市场每日估值指标 (10000 积分尊享)
    利用 trade_date 参数一键拉取 5000+ 股票，极速更新
    """
    try:
        from core.tushare_client import get_ts_client
        from core.database import write_daily_basic
        import datetime
        
        ts = get_ts_client()
        if not ts.available:
            return "Tushare unavailable"
            
        # 确定最近交易日 (简单尝试今日，若无数据则尝试昨日)
        today = datetime.datetime.now()
        target_dates = [today.strftime('%Y%m%d')]
        if today.hour < 16: # 下午4点前，数据可能还没出，尝试昨天
            yesterday = today - datetime.timedelta(days=1)
            target_dates.insert(0, yesterday.strftime('%Y%m%d'))
            
        for d in target_dates:
            ts._rate_limit()
            df = ts.pro.daily_basic(trade_date=d)
            if df is not None and not df.empty:
                write_daily_basic(df)
                # 同时存入 Redis 供选股器秒开
                from core.cache import RedisCache
                cache = RedisCache()
                valuation_dict = df.set_index('ts_code')[['pe', 'pb', 'turnover_rate', 'total_mv']].to_dict('index')
                cache.set(f"snapshot:valuation:{d}", valuation_dict, expire=86400)
                return f"Market valuation synced for {d}: {len(df)} stocks"
        
        return "No valuation data found for recent days"
    except Exception as e:
        return f"Valuation sync error: {str(e)}"
