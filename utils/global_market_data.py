"""
全球与美股市场数据获取模块 — SSM Quantum Pro
整合 Tushare Pro (优先)、AkShare 和 Sina HQ 实时数据接口，支持 Redis 缓存
"""
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from core.tushare_client import get_ts_client
from core.cache import RedisCache

logger = logging.getLogger(__name__)

try:
    _redis = RedisCache()
    if not _redis.ping():
        _redis = None
except Exception:
    _redis = None


def is_us_market_active() -> bool:
    """判断美股是否处于活跃交易时段 (SSM Quantum Pro)"""
    from datetime import datetime
    now = datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    current_min = now.hour * 60 + now.minute
    # 北京时间 21:30 到次日凌晨 5:00 为美股活跃期 (兼容夏令时/冬令时大致区间)
    if current_min >= 1290 or current_min <= 300:
        return True
    return False


def get_global_realtime_data() -> Dict[str, Any]:
    """
    获取全球市场实时行情 (Sina HQ) — 缓存自适应 TTL
    包括：纳斯达克, 标普500, 道琼斯, VIXY(恐慌指数ETF), USD/CNH(离岸人民币), 富时中国A50期货
    """
    now = datetime.now()

    if _redis:
        cached = _redis.get("global:realtime_v1")
        if cached is not None:
            return cached

    result = {}
    
    # 1. 新浪 HQ 接口实时数据
    symbols = {
        "gb_ixic": "纳斯达克",
        "gb_inx": "标普500",
        "gb_dji": "道琼斯",
        "gb_vixy": "恐慌指数VIXY",
        "fx_susdcnh": "离岸人民币",
        "hf_CHA50CFD": "A50期货"
    }
    
    url = f"https://hq.sinajs.cn/list={','.join(symbols.keys())}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    
    try:
        r = requests.get(url, headers=headers, timeout=5)
        lines = r.text.strip().split(';')
        for line in lines:
            if 'hq_str_' not in line or '="' not in line:
                continue
            
            # 提取行情键名
            key = line.split('var hq_str_')[1].split('=')[0]
            val = line.split('="')[1].split(',')
            
            if key in ["gb_ixic", "gb_inx", "gb_dji"]:
                # 美股指数格式: 0:名称, 1:最新价, 2:涨跌幅%, 3:更新时间, 4:涨跌额, 26:昨收
                if len(val) >= 27:
                    result[symbols[key]] = {
                        "price": float(val[1]),
                        "change_pct": float(val[2]),
                        "prev_close": float(val[26]),
                        "time": val[3]
                    }
            elif key == "gb_vixy":
                # VIXY ETF 格式: 0:名称, 1:最新价, 2:涨跌幅%, 3:更新时间, 4:涨跌额, 26:昨收
                if len(val) >= 27 and val[1]:
                    result[symbols[key]] = {
                        "price": float(val[1]),
                        "change_pct": float(val[2]),
                        "prev_close": float(val[26]),
                        "time": val[3]
                    }
            elif key == "fx_susdcnh":
                # 离岸人民币格式: 0:时间, 1:买入, 2:卖出, 3:昨收, 4:最高, 5:最低
                # 计算价格和涨跌幅
                if len(val) >= 4:
                    price = float(val[1])
                    prev = float(val[3])
                    change_pct = (price - prev) / prev * 100 if prev else 0.0
                    result[symbols[key]] = {
                        "price": price,
                        "change_pct": round(change_pct, 4),
                        "prev_close": prev,
                        "time": val[0]
                    }
            elif key == "hf_CHA50CFD":
                # A50期货格式: 0:最新价, 1:盘口, 2:买价, 3:卖价, 4:最高, 5:最低, 7:昨收
                if len(val) >= 8:
                    price = float(val[0])
                    prev = float(val[7]) if float(val[7]) != 0 else price
                    change_pct = (price - prev) / prev * 100 if prev else 0.0
                    result[symbols[key]] = {
                        "price": price,
                        "change_pct": round(change_pct, 3),
                        "prev_close": prev,
                        "time": datetime.now().strftime("%H:%M:%S")
                    }
    except Exception as e:
        logger.error(f"Failed to fetch global realtime data from Sina: {e}")

    # 2. 补充费城半导体指数 (SOX) 实时数据 (高耗时接口，独立缓存 1 小时)
    sox_data = None
    if _redis:
        try:
            sox_data = _redis.get("global:sox_realtime")
        except Exception:
            pass
            
    if sox_data is None:
        try:
            import akshare as ak
            df_sox = ak.macro_global_sox_index()
            if df_sox is not None and not df_sox.empty:
                latest = df_sox.iloc[-1]
                sox_data = {
                    "price": float(latest["最新值"]),
                    "change_pct": float(latest["涨跌幅"]),
                    "prev_close": float(latest["最新值"]) / (1 + float(latest["涨跌幅"]) / 100),
                    "time": str(latest["日期"])
                }
                if _redis:
                    try:
                        _redis.set("global:sox_realtime", sox_data, expire=3600)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Failed to fetch SOX realtime data from Akshare: {e}")

    if sox_data:
        result["费城半导体SOX"] = sox_data

    # 3. 缓存自适应时间
    if result and _redis:
        if now.weekday() >= 5:
            expire_time = 14400  # 周末直接缓存 4 小时
        elif is_us_market_active():
            expire_time = 60     # 美股活跃交易期缓存 60 秒
        else:
            expire_time = 600    # 美股休市期间缓存 10 分钟
            
        try:
            _redis.set("global:realtime_v1", result, expire=expire_time)
        except Exception:
            pass
        
    return result


def get_global_history_data(limit: int = 30) -> Dict[str, pd.DataFrame]:
    """
    获取全球市场指数历史日线数据 — 优先使用 Tushare Pro，缓存 1 小时
    包括：纳斯达克(IXIC), 标普500(SPX), 道琼斯(DJI), 离岸人民币(USD/CNH), 费城半导体(SOX)
    """
    cache_key = f"global:history_v2:{limit}"
    if _redis:
        cached = _redis.get(cache_key)
        if cached is not None:
            try:
                return {k: pd.DataFrame(v) for k, v in cached.items()}
            except Exception as e:
                logger.error(f"Failed to decode cached global history: {e}")
                pass

    result = {}
    ts_client = get_ts_client()
    
    start_date = (datetime.now() - timedelta(days=limit * 2)).strftime('%Y%m%d')
    end_date = datetime.now().strftime('%Y%m%d')

    # 1. 纳斯达克、标普500、道琼斯 (Tushare index_global)
    if ts_client.available:
        for code, name in [("IXIC", "纳斯达克"), ("SPX", "标普500"), ("DJI", "道琼斯")]:
            try:
                ts_client._rate_limit()
                df = ts_client.pro.index_global(ts_code=code, start_date=start_date, end_date=end_date)
                if df is not None and not df.empty:
                    df = df.copy()
                    # 规范格式
                    df.rename(columns={'trade_date': 'date', 'pct_chg': 'change_pct'}, inplace=True)
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                    df = df.sort_values('date').tail(limit).reset_index(drop=True)
                    result[name] = df
            except Exception as e:
                logger.error(f"Tushare index_global failed for {code}: {e}")
                
        # 离岸人民币 (Tushare fx_daily)
        try:
            ts_client._rate_limit()
            df = ts_client.pro.fx_daily(ts_code='USDCNH.FXCM', start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = df.copy()
                # 规范格式，外汇价格以 bid_close 为主
                df.rename(columns={'trade_date': 'date', 'bid_close': 'close'}, inplace=True)
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d').dt.strftime('%Y-%m-%d')
                df['close'] = pd.to_numeric(df['close'], errors='coerce')
                # 计算变动百分比
                df = df.sort_values('date')
                df['change_pct'] = df['close'].pct_change() * 100
                df = df.tail(limit).reset_index(drop=True)
                result["离岸人民币"] = df
        except Exception as e:
            logger.error(f"Tushare fx_daily failed for USDCNH.FXCM: {e}")

    # 2. 兜底策略: 如果 Tushare 获取失败，使用 Akshare 补充美股三大指数历史行情
    import akshare as ak
    for code, name in [(".IXIC", "纳斯达克"), (".INX", "标普500"), (".DJI", "道琼斯")]:
        if name not in result:
            try:
                df = ak.index_us_stock_sina(symbol=code)
                if df is not None and not df.empty:
                    df = df.copy()
                    df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
                    df['close'] = pd.to_numeric(df['close'], errors='coerce')
                    df = df.sort_values('date')
                    df['change_pct'] = df['close'].pct_change() * 100
                    df = df.tail(limit).reset_index(drop=True)
                    result[name] = df
            except Exception as e:
                logger.error(f"Akshare fallback index_us_stock_sina failed for {code}: {e}")

    # 3. 费城半导体 (SOX) 历史行情 (Tushare无，使用 Akshare 补充)
    try:
        df_sox = ak.macro_global_sox_index()
        if df_sox is not None and not df_sox.empty:
            df_sox = df_sox.copy()
            df_sox.rename(columns={'日期': 'date', '最新值': 'close', '涨跌幅': 'change_pct'}, inplace=True)
            df_sox['date'] = pd.to_datetime(df_sox['date']).dt.strftime('%Y-%m-%d')
            df_sox['close'] = pd.to_numeric(df_sox['close'], errors='coerce')
            df_sox['change_pct'] = pd.to_numeric(df_sox['change_pct'], errors='coerce')
            df_sox = df_sox.sort_values('date').tail(limit).reset_index(drop=True)
            result["费城半导体SOX"] = df_sox
    except Exception as e:
        logger.error(f"Akshare macro_global_sox_index failed: {e}")

    # 4. 离岸人民币兜底 (Sina HQ 模拟或 FX Spot 报价模拟)
    if "离岸人民币" not in result:
        try:
            # 临时生成一个根据实时数据倒推的简版历史，或者通过 ak.fx_spot_quote 模拟
            # 我们直接用实时数据兜底
            rt = get_global_realtime_data()
            if "离岸人民币" in rt:
                item = rt["离岸人民币"]
                df = pd.DataFrame([{
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "close": item["price"],
                    "change_pct": item["change_pct"]
                }])
                result["离岸人民币"] = df
        except Exception as e:
            logger.error(f"Fallback fx data failed: {e}")

    # 写入缓存
    if result and _redis:
        try:
            serializable_result = {k: v.to_dict(orient="records") for k, v in result.items()}
            _redis.set(cache_key, serializable_result, expire=3600)
        except Exception as e:
            logger.error(f"Failed to cache global history: {e}")
            pass

    return result
