
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
def get_dynamic_ttl(base_ttl=300):
    """根据交易时段自适应计算 TTL (非交易时段自动延长)"""
    if is_market_closed():
        return 14400 # 4小时
    return base_ttl

try:
    from core.cache import RedisCache
    _redis = RedisCache()
    if not _redis.ping():
        _redis = None
    else:
        # 包装 _redis.set 以支持自适应 TTL
        _original_set = _redis.set
        def _adaptive_redis_set(key, val, expire=300):
            if expire is not None and expire <= 3600:
                expire = get_dynamic_ttl(expire)
            return _original_set(key, val, expire=expire)
        _redis.set = _adaptive_redis_set
except Exception:
    _redis = None

def _get_cache_path(symbol, period):
    return os.path.join(CACHE_DIR, f"kline_{symbol}_{period}.pkl")

def _load_from_cache(symbol, period, ttl_seconds=600):
    cache_path = _get_cache_path(symbol, period)
    if os.path.exists(cache_path):
        # 非交易时段自适应调大 TTL
        dynamic_ttl = get_dynamic_ttl(ttl_seconds)
        if time.time() - os.path.getmtime(cache_path) < dynamic_ttl:
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

def calculate_advanced_trading_signals(symbol):
    """
    计算基于行业先进做法的买卖点及风控目标 (SSM Quantum Pro)
    """
    df = fetch_kline(symbol, period='daily', datalen=100)
    if df.empty or len(df) < 20:
        return {
            "signal": "数据不足",
            "buy_zone": "—",
            "stop_loss": "—",
            "take_profit": "—",
            "rsi": 50.0,
            "macro_trend": "未知"
        }
    
    df = df.copy()
    # 确保价格数据为数值型
    for col in ['开盘', '最高', '最低', '收盘', '成交量']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
    # 计算 ATR-14
    high_low = df['最高'] - df['最低']
    high_close = (df['最高'] - df['收盘'].shift()).abs()
    low_close = (df['最低'] - df['收盘'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(window=14).mean()
    
    # 计算 RSI-14 (自愈处理分母为0)
    close_delta = df['收盘'].diff()
    up = close_delta.clip(lower=0)
    down = -1 * close_delta.clip(upper=0)
    ma_up = up.rolling(window=14).mean()
    ma_down = down.rolling(window=14).mean()
    rs = ma_up / ma_down.replace(0, 1e-6)
    df['RSI'] = 100.0 - (100.0 / (1.0 + rs))
    
    # 填充热身期的空值
    df['ATR'] = df['ATR'].bfill().fillna(0.0)
    df['RSI'] = df['RSI'].fillna(50.0)
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    close = float(latest['收盘'])
    atr = float(latest['ATR'])
    rsi = float(latest['RSI'])
    
    # 获取 MA 均线
    ma5 = float(latest.get('MA5', close))
    ma20 = float(latest.get('MA20', close))
    ma60 = float(latest.get('MA60', close))
    
    # 1. 判定大周期大势 (Regime Filter: 收盘价是否站上生命线 MA60)
    macro_trend_up = close >= ma60
    
    # 2. 决策逻辑
    # 🟢 强买点：周线级别偏多 + RSI超卖回踩(< 45) + 日线均线偏多或者拐头向上 (MA5 > MA20)
    if macro_trend_up and rsi < 45 and ma5 >= ma20:
        signal = "🟢 建议分批建仓 (大趋势向上+日线回踩超卖)"
        stop_loss = round(close - 1.5 * atr, 2)
        take_profit = round(close + 3.0 * atr, 2)
        buy_zone = f"{round(close - 0.5 * atr, 2)} ~ {round(close + 0.25 * atr, 2)}"
    # 🔴 减仓卖点：日线级别死叉或者股价跌破生命线 MA20
    elif (prev.get('MA5', ma5) >= prev.get('MA20', ma20) and ma5 < ma20) or (close < ma20 and prev.get('收盘', close) >= prev.get('MA20', ma20)):
        signal = "🔴 建议减仓避险 (均线死叉或破位20日均线)"
        stop_loss = "—"
        take_profit = "—"
        buy_zone = "—"
    # 🔵 持仓观望/超买警示
    elif macro_trend_up:
        if rsi > 75:
            signal = "🟡 建议部分止盈 (日线RSI超买高位震荡)"
        else:
            signal = "🔵 建议继续持股 (宏观多头格局但处于拉升中)"
        stop_loss = round(close - 2.0 * atr, 2) # 宽幅移动止损
        take_profit = "—"
        buy_zone = "—"
    # ⚪ 逆势观望
    else:
        signal = "⚪ 建议空仓观望 (生命线下方下行趋势)"
        stop_loss = "—"
        take_profit = "—"
        buy_zone = "—"
        
    return {
        "signal": signal,
        "buy_zone": buy_zone,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "rsi": round(rsi, 1),
        "macro_trend": "多头" if macro_trend_up else "空头"
    }

def fetch_trading_signals(symbol):
    """基于 K线数据计算简单的技术信号"""
    try:
        adv = calculate_advanced_trading_signals(symbol)
        if adv["signal"] == "数据不足":
            return "数据不足，无法生成信号"
        
        # 兼容原有的字符串返回，同时丰富内容供 AI 报告消费
        desc = f"{adv['signal']} (日线RSI: {adv['rsi']}, 大趋势: {adv['macro_trend']})"
        if adv["stop_loss"] != "—":
            desc += f"，建议建仓价区: {adv['buy_zone']}，风控防守止损位: {adv['stop_loss']}，第一止盈目标位: {adv['take_profit']}"
        return desc
    except Exception as e:
        return f"信号计算异常: {e}"

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

def _fetch_sina_batch_quotes(symbols):
    """利用新浪批量行情接口拉取多个股票的行情 (SSM Quantum Pro)"""
    import requests
    import re
    results = {}
    
    # 格式化 symbol，确保带上 sh/sz 前缀
    formatted_symbols = []
    for s in symbols:
        s = s.strip()
        if not s.startswith(('sh', 'sz')):
            s = ("sh" if s.startswith('6') else "sz") + s
        formatted_symbols.append(s)
        
    # 分批，每批最多 80 个
    batch_size = 80
    for i in range(0, len(formatted_symbols), batch_size):
        batch = formatted_symbols[i:i+batch_size]
        url = f"https://hq.sinajs.cn/list={','.join(batch)}"
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        try:
            r = requests.get(url, headers=headers, timeout=5)
            lines = r.text.strip().split(';')
            for line in lines:
                if 'hq_str_' not in line or '="' not in line:
                    continue
                match = re.search(r'hq_str_((?:sh|sz)\d+)\s*=\s*"([^"]+)"', line)
                if match:
                    sym_with_prefix = match.group(1)
                    pure_sym = sym_with_prefix[2:]  # 去掉 sh/sz
                    parts = match.group(2).split(',')
                    if len(parts) > 3:
                        open_p = float(parts[1])
                        prev_close = float(parts[2])
                        price = float(parts[3])
                        
                        # 如果没有最新成交价（停牌），用昨收
                        if price == 0:
                            price = prev_close
                            
                        # 计算涨跌幅
                        change_pct = (price - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
                        
                        results[pure_sym] = {
                            "最新价": price,
                            "涨跌幅": round(change_pct, 2),
                            "price": price,
                            "change_pct": round(change_pct, 2),
                            "换手率": 0.0,
                            "量比": 1.0
                        }
        except Exception as e:
            print(f"Sina batch quotes fetch error: {e}")
            
    return results

def _fetch_single_quote(symbol):
    """为并发获取获取单只股票的当前价格和涨跌幅 (兜底防御)"""
    df = fetch_kline(symbol, period='daily', datalen=5)
    if not df.empty:
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        pct = (latest['收盘'] - prev['收盘']) / prev['收盘'] * 100 if prev['收盘'] > 0 else 0
        return symbol, {
            "最新价": latest['收盘'],
            "涨跌幅": round(pct, 2),
            "price": latest['收盘'],
            "change_pct": round(pct, 2),
            "换手率": latest.get('换手率', 0.0) if '换手率' in latest else 0.0,
            "量比": latest.get('量比', 0.0) if '量比' in latest else 0.0
        }
    return symbol, None

def fetch_quotes_concurrent(symbols, max_workers=10):
    """利用全市场快照及批量接口优化行情获取 (SSM Quantum Pro)"""
    results = {}
    if not symbols:
        return results
        
    # 格式化 symbols 为纯数字代码
    pure_symbols = []
    for s in symbols:
        s = s.strip()
        if s.startswith(('sh', 'sz')):
            s = s[2:]
        pure_symbols.append(s)
        
    # 1. 尝试从全市场快照（已被 main.py 缓存）中查找
    try:
        from main import get_full_market_data
        snapshot_df = get_full_market_data()
        if snapshot_df is not None and not snapshot_df.empty:
            snapshot_df = snapshot_df.copy()
            # 确保代码列为字符串并去空
            snapshot_df['代码'] = snapshot_df['代码'].astype(str).str.strip()
            
            # 列名映射兼容
            col_map = {
                '最新价': ['最新价', 'close', 'trade'],
                '涨跌幅': ['涨跌幅', 'pct_chg', 'changepercent'],
                '换手率': ['换手率', 'turnover_rate', 'turnoverratio'],
                '量比': ['量比', 'vol_ratio', 'volume_ratio']
            }
            
            def get_col_val(row, target_key, default_val=0.0):
                for col_name in col_map.get(target_key, []):
                    if col_name in row.index:
                        val = row[col_name]
                        if pd.notna(val):
                            try:
                                return float(val)
                            except:
                                pass
                return default_val

            # 对匹配成功的代码进行处理
            matched = snapshot_df[snapshot_df['代码'].isin(pure_symbols)]
            for _, row in matched.iterrows():
                sym = row['代码']
                price = get_col_val(row, '最新价', 0.0)
                change_pct = get_col_val(row, '涨跌幅', 0.0)
                turnover = get_col_val(row, '换手率', 0.0)
                vol_ratio = get_col_val(row, '量比', 1.0)
                
                results[sym] = {
                    "最新价": price,
                    "涨跌幅": round(change_pct, 2),
                    "price": price,
                    "change_pct": round(change_pct, 2),
                    "换手率": turnover,
                    "量比": vol_ratio
                }
    except Exception as e:
        print(f"Error reading market snapshot: {e}")
        
    # 2. 针对缺失的代码，使用新浪批量行情接口进行补全
    missing = [s for s in pure_symbols if s not in results]
    if missing:
        try:
            sina_results = _fetch_sina_batch_quotes(missing)
            results.update(sina_results)
        except Exception as e:
            print(f"Sina batch fallback error: {e}")
            
    # 3. 针对仍然缺失的代码（极少见），使用原有的单股 K 线拉取做最后底线防御
    still_missing = [s for s in pure_symbols if s not in results]
    if still_missing:
        fallback_results = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(still_missing), max_workers)) as executor:
            future_to_sym = {executor.submit(_fetch_single_quote, sym): sym for sym in still_missing}
            for future in concurrent.futures.as_completed(future_to_sym):
                sym, data = future.result()
                if data:
                    fallback_results[sym] = data
        results.update(fallback_results)
        
    # 4. 针对传入的格式做 key 兼容
    final_results = {}
    for original_sym in symbols:
        original_sym_clean = original_sym.strip()
        pure_sym = original_sym_clean
        if pure_sym.startswith(('sh', 'sz')):
            pure_sym = pure_sym[2:]
        if pure_sym in results:
            final_results[original_sym_clean] = results[pure_sym]
            
    return final_results
