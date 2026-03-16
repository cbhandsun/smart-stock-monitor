
import pandas as pd
import requests
import os
import time
import concurrent.futures

CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Redis L1 缓存
try:
    from core.cache import RedisCache
    _redis = RedisCache()
    if not _redis.ping():
        _redis = None
except Exception:
    _redis = None

def _get_cache_path(symbol, period):
    return os.path.join(CACHE_DIR, f"kline_{symbol}_{period}.pkl")

def _load_from_cache(symbol, period, ttl_seconds=300):
    cache_path = _get_cache_path(symbol, period)
    if os.path.exists(cache_path):
        # 如果缓存未过期 (默认5分钟)
        if time.time() - os.path.getmtime(cache_path) < ttl_seconds:
            try:
                return pd.read_pickle(cache_path)
            except Exception:
                pass
    return None

def _save_to_cache(df, symbol, period):
    if not df.empty:
        try:
            df.to_pickle(_get_cache_path(symbol, period))
        except Exception as e:
            print(f"Cache save error: {e}")

# 代理处理
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

# 时间周期映射 (scale: 分钟)
TIME_PERIOD_MAP = {
    '1min': 1,
    '5min': 5,
    '15min': 15,
    '30min': 30,
    '60min': 60,
    'daily': 240,  # 日线使用240分钟
    'weekly': 240,  # 周线需要特殊处理
    'monthly': 240  # 月线需要特殊处理
}


def fetch_kline(symbol, period='daily', datalen=100):
    """
    获取K线数据 — Redis L1 (300s) + 文件 L2
    symbol 格式: sh601318, sz002428
    """
    # 确保带上前缀
    if not symbol.startswith(('sh', 'sz')):
        symbol = "sh" + symbol if symbol.startswith('6') else "sz" + symbol
    
    scale = TIME_PERIOD_MAP.get(period, 240)
    
    # 对于周线和月线，先获取日线数据再转换
    if period in ['weekly', 'monthly']:
        return fetch_kline_weekly_monthly(symbol, period, datalen)
    
    # L1: Redis
    redis_key = f"kline:{symbol}:{period}:{datalen}"
    if _redis:
        cached = _redis.get(redis_key)
        if cached is not None:
            return cached.tail(datalen) if len(cached) > datalen else cached

    # L2: 文件缓存
    cached_df = _load_from_cache(symbol, period)
    if cached_df is not None:
        result = cached_df.tail(datalen) if len(cached_df) > datalen else cached_df
        if _redis:
            _redis.set(redis_key, result, expire=300)
        return result
    
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={datalen}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        if not data or not isinstance(data, list): 
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        df.rename(columns={
            'day': '日期', 
            'open': '开盘', 
            'high': '最高', 
            'low': '最低', 
            'close': '收盘', 
            'volume': '成交量'
        }, inplace=True)
        
        for col in ['开盘', '最高', '最低', '收盘', '成交量']:
            df[col] = pd.to_numeric(df[col])
        
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA60'] = df['收盘'].rolling(window=60).mean()
        df['周期'] = period
        
        # 写入双层缓存
        _save_to_cache(df, symbol, period)
        result = df.tail(datalen) if len(df) > datalen else df
        if _redis:
            _redis.set(redis_key, result, expire=300)
        return result
    except Exception as e:
        print(f"Sina KLine fetch error for {symbol}: {e}")
        return pd.DataFrame()


def fetch_kline_weekly_monthly(symbol, period='weekly', datalen=100):
    """
    获取周线或月线数据
    通过akshare获取，然后转换为统一格式
    """
    try:
        # 尝试读取缓存 (周月线缓存时间可以长一点，比如 1小时)
        cached_df = _load_from_cache(symbol, period, ttl_seconds=3600)
        if cached_df is not None:
            return cached_df.tail(datalen) if len(cached_df) > datalen else cached_df

        # 提取纯数字代码
        code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
        
        if period == 'weekly':
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=code, period="weekly", start_date="20200101", adjust="qfq")
        else:  # monthly
            import akshare as ak
            df = ak.stock_zh_a_hist(symbol=code, period="monthly", start_date="20200101", adjust="qfq")
        
        if df.empty:
            return pd.DataFrame()
        
        # 重命名列以统一格式
        df = df.rename(columns={
            '日期': '日期',
            '开盘': '开盘',
            '收盘': '收盘',
            '最高': '最高',
            '最低': '最低',
            '成交量': '成交量',
            '成交额': '成交额',
            '振幅': '振幅',
            '涨跌幅': '涨跌幅',
            '涨跌额': '涨跌额',
            '换手率': '换手率'
        })
        
        # 确保数值类型正确
        for col in ['开盘', '最高', '最低', '收盘', '成交量']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 计算均线
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA60'] = df['收盘'].rolling(window=60).mean()
        
        # 添加周期标识
        df['周期'] = period
        
        # 限制返回数据条数
        _save_to_cache(df, symbol, period)
        if len(df) > datalen:
            df = df.tail(datalen).reset_index(drop=True)
        
        return df
    except Exception as e:
        print(f"Fetch {period} data error for {symbol}: {e}")
        return pd.DataFrame()

def fetch_trading_signals(symbol):
    """基于 K线数据计算简单的技术信号"""
    df = fetch_kline(symbol)
    if df.empty or len(df) < 2:
        return "数据不足，无法生成信号"
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    try:
        if prev['MA5'] < prev['MA20'] and latest['MA5'] > latest['MA20']:
            return "【买入信号】MA5 金叉 MA20，短期趋势走强"
        elif prev['MA5'] > prev['MA20'] and latest['MA5'] < latest['MA20']:
            return "【卖出信号】MA5 死叉 MA20，短期趋势转弱"
        
        if latest['收盘'] > latest['MA20']:
            return "【持仓/看多】股价站稳 20 日均线"
        else:
            return "【观望/看空】股价处于均线下方压制"
    except:
        return "信号计算异常"

def fetch_research_reports(symbol):
    """获取研报 (akshare) - 增加异常处理"""
    try:
        # 提取纯数字代码
        code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
        import akshare as ak
        df = ak.stock_zyjs_report_em(symbol=code)
        if not df.empty:
            return df.head(3)
        return pd.DataFrame()
    except:
        return pd.DataFrame()

def _fetch_single_quote(symbol):
    """为并发获取获取单只股票的当前价格和涨跌幅"""
    df = fetch_kline(symbol, period='daily', datalen=5)
    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        pct = (latest['收盘'] - prev['收盘']) / prev['收盘'] * 100 if prev['收盘'] > 0 else 0
        return symbol, {
            "最新价": latest['收盘'],
            "涨跌幅": round(pct, 2),
            "换手率": latest.get('换手率', 0.0) if '换手率' in latest else 0.0,
            "量比": latest.get('量比', 0.0) if '量比' in latest else 0.0
        }
    return symbol, None

def fetch_quotes_concurrent(symbols, max_workers=10):
    """利用线程池并发获取行情，并借助缓存机制达到秒开"""
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_sym = {executor.submit(_fetch_single_quote, sym): sym for sym in symbols}
        for future in concurrent.futures.as_completed(future_to_sym):
            sym, data = future.result()
            if data:
                results[sym] = data
    return results
