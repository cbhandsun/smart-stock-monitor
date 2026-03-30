
import pandas as pd
import requests
import os
import time
import concurrent.futures

try:
    import streamlit as _st
except ImportError:
    _st = None

CACHE_DIR = "data/cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def is_market_closed():
    """判断当前是否为非交易时间 (简单判断: 周末或 9:30-15:00 以外)"""
    from datetime import datetime
    now = datetime.now()
    if now.weekday() >= 5: # 周末
        return True
    # 转换为分钟 (9:30 = 570, 15:00 = 900)
    current_min = now.hour * 60 + now.minute
    if current_min < 570 or current_min > 910: # 稍微多跑10分钟以防收盘数据延迟
        return True
    return False

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

def _load_from_cache(symbol, period, ttl_seconds=600):
    cache_path = _get_cache_path(symbol, period)
    if os.path.exists(cache_path):
        # 如果缓存未过期 (默认10分钟)
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

def get_last_timestamp(symbol, period):
    """获取缓存中最后一条数据的时间戳"""
    cache_path = _get_cache_path(symbol, period)
    if os.path.exists(cache_path):
        try:
            df = pd.read_pickle(cache_path)
            if not df.empty:
                return df['日期'].iloc[-1]
        except:
            pass
    return None

def merge_kline_data(old_df, new_df):
    """合并新旧K线数据并去重"""
    if old_df is None or old_df.empty:
        return new_df
    if new_df is None or new_df.empty:
        return old_df
    
    combined = pd.concat([old_df, new_df])
    # 确保日期列是字符串以一致比较，或确保格式一致
    combined['日期'] = combined['日期'].astype(str)
    combined = combined.drop_duplicates(subset=['日期'], keep='last')
    combined = combined.sort_values('日期')
    return combined.reset_index(drop=True)

def _recalculate_indicators(df):
    """为DataFrame重新计算常用技术指标"""
    if df.empty: return df
    try:
        # 确保收盘价为数值
        df['收盘'] = pd.to_numeric(df['收盘'], errors='coerce')
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA60'] = df['收盘'].rolling(window=60).mean()
    except Exception as e:
        print(f"Indicator calculation error: {e}")
    return df

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


def _fetch_kline_impl(symbol, period='daily', datalen=100):
    """
    获取K线数据 — 多层缓存 + 多数据源
    优先级: Redis → Tushare+PG → Sina (fallback)
    symbol 格式: sh601318, sz002428, 601318
    """
    # 确保带上前缀
    if not symbol.startswith(('sh', 'sz')):
        symbol = "sh" + symbol if symbol.startswith('6') else "sz" + symbol

    if period in ['weekly', 'monthly']:
        return fetch_kline_weekly_monthly(symbol, period, datalen)

    import datetime
    now = datetime.datetime.now()
    # 获取上一个交易日 (推测逻辑：如果是周六日，则为上周五；如果是平时16点前，则为昨天)
    if now.weekday() >= 5: # 周六日
        target_latest = (now - datetime.timedelta(days=now.weekday()-4)).strftime('%Y-%m-%d')
    elif now.hour < 16: # 平时下午4点前
        target_latest = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        target_latest = now.strftime('%Y-%m-%d')

    # L1: Redis 热缓存
    redis_key = f"kline:{symbol}:{period}:{datalen}"
    if _redis:
        cached = _redis.get(redis_key)
        if cached is not None:
            return cached.tail(datalen) if len(cached) > datalen else cached

    # 日线: 优先 Tushare + PG
    if period == 'daily':
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            if ts.available:
                df = ts.get_daily(symbol, limit=max(datalen, 200))
                if df is not None and not df.empty:
                    # 校验 Tushare 数据是否足够新 (判定标准：最后日期必须 >= target_latest)
                    last_dt = str(df['日期'].iloc[-1]).split(' ')[0]
                    if last_dt < target_latest:
                        print(f"Tushare data for {symbol} is stale ({last_dt} < {target_latest}). Attempting AkShare fallback...")
                        try:
                            import akshare as ak
                            pure_code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
                            # 补全从 stale 到 target 的断层
                            start_patch = (pd.to_datetime(last_dt) + datetime.timedelta(days=1)).strftime('%Y%m%d')
                            patch_df = ak.stock_zh_a_hist(symbol=pure_code, period='daily', start_date=start_patch)
                            if not patch_df.empty:
                                patch_df.rename(columns={'日期': '日期', '开盘': '开盘', '最高': '最高', '最低': '最低', '收盘': '收盘', '成交量': '成交量'}, inplace=True)
                                df = merge_kline_data(df, patch_df)
                                print(f"Successfully patched {symbol} with {len(patch_df)} days from AkShare.")
                        except Exception as patch_e:
                            print(f"AkShare patch failed: {patch_e}")
                    
                    df = _recalculate_indicators(df)
                    df['周期'] = period
                    _save_to_cache(df, symbol, period)
                    result = df.tail(datalen) if len(df) > datalen else df
                    if _redis:
                        _redis.set(redis_key, result, expire=300)
                    return result
        except Exception as e:
            print(f"Tushare daily fallback: {e}")

    # L2: 文件缓存
    cached_df = _load_from_cache(symbol, period, ttl_seconds=3600*24*7) # 这里的TTL增大，因为我们会增量更新
    
    # 检查是否需要同步 (只有当缓存的数据日期已经是最近的交易日时，才跳过同步)
    last_date = get_last_timestamp(symbol, period)
    
    if is_market_closed() and last_date and str(last_date).split(' ')[0] >= target_latest:
        if cached_df is not None and len(cached_df) >= datalen:
            result = cached_df.tail(datalen)
            if _redis:
                _redis.set(redis_key, result, expire=300)
            return result

    # 尝试增量同步 (仅针对 Tushare 日线)
    if period == 'daily' and last_date:
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            if ts.available:
                import datetime
                start_date = (pd.to_datetime(last_date) + datetime.timedelta(days=1)).strftime('%Y%m%d')
                if start_date <= datetime.datetime.now().strftime('%Y%m%d'):
                    new_df = ts.get_daily(symbol, start_date=start_date)
                    if new_df is not None and not new_df.empty:
                        new_df['周期'] = period
                        full_df = merge_kline_data(cached_df, new_df)
                        _save_to_cache(full_df, symbol, period)
                        result = full_df.tail(datalen)
                        if _redis:
                            _redis.set(redis_key, result, expire=300)
                        return result
        except Exception as e:
            print(f"Incremental sync error for {symbol}: {e}")

    # Fallback: 无效缓存或无法增量，执行全量拉取
    if cached_df is not None and len(cached_df) >= datalen:
        # 如果缓存足够新 (10分钟内)，直接返回
        if time.time() - os.path.getmtime(_get_cache_path(symbol, period)) < 600:
            result = cached_df.tail(datalen)
            if _redis:
                _redis.set(redis_key, result, expire=300)
            return result

    # Sina fallback (日线 + 分钟线)
    scale = TIME_PERIOD_MAP.get(period, 240)
    fetch_len = max(datalen, 200)
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale={scale}&ma=no&datalen={fetch_len}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        if not data or not isinstance(data, list):
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df.rename(columns={
            'day': '日期', 'open': '开盘', 'high': '最高',
            'low': '最低', 'close': '收盘', 'volume': '成交量'
        }, inplace=True)

        for col in ['开盘', '最高', '最低', '收盘', '成交量']:
            df[col] = pd.to_numeric(df[col])

        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        df['MA60'] = df['收盘'].rolling(window=60).mean()
        df['周期'] = period

        _save_to_cache(df, symbol, period)
        result = df.tail(datalen) if len(df) > datalen else df
        if _redis:
            _redis.set(redis_key, result, expire=300)
        return result
    except Exception as e:
        print(f"Sina KLine fetch error for {symbol}: {e}")
        return pd.DataFrame()


def fetch_kline(symbol, period='daily', datalen=100):
    """缓存包装器 — 优先 st.cache_data (10min TTL)"""
    if _st is not None and hasattr(_st, 'cache_data'):
        return _cached_fetch_kline(symbol, period, datalen)
    return _fetch_kline_impl(symbol, period, datalen)


if _st is not None and hasattr(_st, 'cache_data'):
    @_st.cache_data(ttl=600, show_spinner=False)
    def _cached_fetch_kline(symbol, period='daily', datalen=100):
        return _fetch_kline_impl(symbol, period, datalen)
else:
    _cached_fetch_kline = _fetch_kline_impl


def fetch_kline_weekly_monthly(symbol, period='weekly', datalen=100):
    """
    获取周线或月线数据
    优先级: Redis → Tushare+PG → Sina日线聚合 (fallback)
    """
    try:
        # L1: Redis
        redis_key = f"kline:{symbol}:{period}:{datalen}"
        if _redis:
            cached = _redis.get(redis_key)
            if cached is not None:
                return cached.tail(datalen) if len(cached) > datalen else cached

        # Tushare + PG
        try:
            from core.tushare_client import get_ts_client
            ts = get_ts_client()
            if ts.available:
                if period == 'weekly':
                    df = ts.get_weekly(symbol, limit=max(datalen, 100))
                else:
                    df = ts.get_monthly(symbol, limit=max(datalen, 60))
                if df is not None and not df.empty:
                    df['周期'] = period
                    _save_to_cache(df, symbol, period)
                    result = df.tail(datalen) if len(df) > datalen else df
                    if _redis:
                        _redis.set(redis_key, result, expire=3600)
                    return result
        except Exception as e:
            print(f"Tushare {period} fallback: {e}")

        # L2: 文件缓存
        cached_df = _load_from_cache(symbol, period, ttl_seconds=3600)
        if cached_df is not None and len(cached_df) >= datalen:
            result = cached_df.tail(datalen)
            if _redis:
                _redis.set(redis_key, result, expire=3600)
            return result

        # Sina fallback: 拉日线数据本地聚合
        if not symbol.startswith(('sh', 'sz')):
            symbol = "sh" + symbol if symbol[0] == '6' else "sz" + symbol

        daily_need = max(datalen * (5 if period == 'weekly' else 22), 500)
        url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen={daily_need}"
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
        if not data or not isinstance(data, list):
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df.rename(columns={
            'day': '日期', 'open': '开盘', 'high': '最高',
            'low': '最低', 'close': '收盘', 'volume': '成交量'
        }, inplace=True)
        for col in ['开盘', '最高', '最低', '收盘', '成交量']:
            df[col] = pd.to_numeric(df[col])

        df['日期'] = pd.to_datetime(df['日期'])
        df = df.set_index('日期').sort_index()

        rule = 'W-FRI' if period == 'weekly' else 'ME'
        agg = df.resample(rule).agg({
            '开盘': 'first', '最高': 'max', '最低': 'min',
            '收盘': 'last', '成交量': 'sum',
        }).dropna(subset=['开盘'])

        agg = agg.reset_index()
        agg['日期'] = agg['日期'].dt.strftime('%Y-%m-%d')
        agg['MA5'] = agg['收盘'].rolling(5).mean()
        agg['MA20'] = agg['收盘'].rolling(20).mean()
        agg['MA60'] = agg['收盘'].rolling(60).mean()
        agg['周期'] = period

        _save_to_cache(agg, symbol, period)
        result = agg.tail(datalen).reset_index(drop=True) if len(agg) > datalen else agg
        if _redis:
            _redis.set(redis_key, result, expire=3600)
        return result
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
    """获取研报 (akshare) — Redis 缓存 3600s"""
    cache_key = f"research:{symbol}"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            return cached
    try:
        # 提取纯数字代码
        code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
        import akshare as ak
        df = ak.stock_zyjs_report_em(symbol=code)
        if not df.empty:
            result = df.head(3)
            if _redis:
                _redis.set(cache_key, result, expire=3600)
            return result
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
