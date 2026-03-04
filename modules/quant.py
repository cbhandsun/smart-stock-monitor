import pandas as pd
import numpy as np

def calculate_metrics(df):
    """
    计算量化指标：
    1. 波动率 (Volatility)
    2. 最大回撤 (Max Drawdown)
    3. RSI (相对强弱指标)
    4. MACD
    """
    if df.empty: return {}
    
    # 确保按日期升序
    df = df.sort_values('日期')
    close = df['收盘']
    
    # 1. 波动率 (年化)
    returns = close.pct_change()
    volatility = returns.std() * np.sqrt(252) * 100
    
    # 2. 最大回撤
    roll_max = close.cummax()
    drawdown = (close - roll_max) / roll_max
    max_drawdown = drawdown.min() * 100
    
    # 3. RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]
    
    # 4. MACD (12, 26, 9)
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    hist = macd - signal
    
    return {
        'volatility_ann': volatility,
        'max_drawdown': max_drawdown,
        'rsi': current_rsi,
        'macd': macd.iloc[-1],
        'macd_signal': signal.iloc[-1],
        'macd_hist': hist.iloc[-1]
    }
