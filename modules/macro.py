import requests
import pandas as pd

# Redis L1 缓存
try:
    from core.cache import RedisCache
    _redis = RedisCache()
    if not _redis.ping():
        _redis = None
except Exception:
    _redis = None

def get_macro_indicators():
    """
    获取 A股核心宏观与流动性指标 — Redis 缓存 120s
    1. 北向资金 (模拟/或通过 akshare 获取)
    2. 富时中国A50期货 (Sentiment)
    3. 美元/离岸人民币 (USD/CNH) - 资金流向风向标
    """
    # L1: Redis
    if _redis:
        cached = _redis.get("macro:indicators_v2")
        if cached is not None:
            return cached

    indicators = {}
    
    # --- 1. Sina JS 实时行情 ---
    try:
        # fx_susdcnh (离岸人民币), hf_CHA50CFD (A50期货)
        url = "https://hq.sinajs.cn/list=fx_susdcnh,hf_CHA50CFD"
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        r = requests.get(url, headers=headers, timeout=3)
        lines = r.text.strip().split(';')
        
        for line in lines:
            if 'fx_susdcnh' in line and '="' in line:
                val = line.split('="')[1].split(',')
                price = float(val[1])
                # Sina FX format change_pct might be index 10 or calculated
                indicators['USD/CNH'] = {'price': price, 'change_pct': 0} 
                
            elif 'hf_CHA50CFD' in line and '="' in line:
                val = line.split('="')[1].split(',')
                price = float(val[0])
                prev = float(val[7]) if len(val)>7 and float(val[7])!=0 else price
                change = (price - prev) / prev * 100 if prev else 0
                indicators['富时中国A50'] = {'price': price, 'change_pct': change}
                
    except Exception as e:
        print(f"Macro fetch error (Sina): {e}")

    # --- 2. 北向资金 (Tushare 沪深港通) ---
    try:
        from core.tushare_client import get_ts_client
        ts = get_ts_client()
        if ts.available:
            hsgt = ts.get_hsgt_flow(days=5)
            if hsgt is not None and not hsgt.empty:
                latest = hsgt.iloc[-1]
                # north_money = 沪股通+深股通 净买入 (百万)
                hgt = float(latest.get('hgt', 0) or 0)  # 沪股通
                sgt = float(latest.get('sgt', 0) or 0)  # 深股通
                north_total = hgt + sgt  # 百万
                prev = hsgt.iloc[-2] if len(hsgt) > 1 else latest
                prev_total = float(prev.get('hgt', 0) or 0) + float(prev.get('sgt', 0) or 0)
                change = north_total - prev_total
                indicators['北向资金'] = {
                    'price': round(north_total / 100, 2),  # 转为亿
                    'change_pct': round(change / abs(prev_total) * 100, 1) if prev_total != 0 else 0,
                    'note': f"沪{hgt/100:.1f}亿 深{sgt/100:.1f}亿"
                }
            else:
                indicators['北向资金'] = {'price': 0.0, 'change_pct': 0, 'note': '非交易时段'}
    except Exception as e:
        print(f"北向资金获取失败: {e}")
        indicators['北向资金(预估)'] = {'price': 0.0, 'change_pct': 0, 'note': '数据待更新'}

    if indicators and _redis:
        _redis.set("macro:indicators_v2", indicators, expire=120)

    return indicators
