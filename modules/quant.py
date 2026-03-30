import pandas as pd
import numpy as np

def calculate_metrics(df):
    """
    计算量化指标：
    1. 波动率 (Volatility)
    2. 最大回撤 (Max Drawdown)
    3. RSI (相对强弱指标)
    4. MACD
    5. 布林带 (Bollinger Bands)
    6. KDJ指标
    7. CCI指标
    8. OBV指标
    9. DMI指标
    """
    if df.empty: return {}
    
    # 确保按日期升序
    df = df.sort_values('日期')
    close = df['收盘']
    high = df['最高']
    low = df['最低']
    volume = df.get('成交量', pd.Series([0] * len(df), index=df.index))
    
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
    
    # 5. 布林带 (Bollinger Bands) - 20日，2倍标准差
    bb_middle = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    bb_upper = bb_middle + 2 * bb_std
    bb_lower = bb_middle - 2 * bb_std
    bb_width = (bb_upper - bb_lower) / bb_middle * 100  # 带宽百分比
    bb_percent = (close - bb_lower) / (bb_upper - bb_lower) * 100  # %B指标
    
    # 6. KDJ指标
    # RSV = (收盘价 - N日内最低价) / (N日内最高价 - N日内最低价) × 100
    n = 9
    low_n = low.rolling(window=n).min()
    high_n = high.rolling(window=n).max()
    rsv = (close - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)  # 处理除零
    
    # K值 = 2/3 × 前一日K值 + 1/3 × 当日RSV
    # D值 = 2/3 × 前一日D值 + 1/3 × 当日K值
    k = rsv.ewm(com=2, adjust=False).mean()  # 简化计算
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d
    
    # 7. CCI指标 (Commodity Channel Index) - 20日
    tp = (high + low + close) / 3  # 典型价格
    tp_ma = tp.rolling(window=20).mean()
    tp_std = tp.rolling(window=20).std()
    cci = (tp - tp_ma) / (0.015 * tp_std)
    cci = cci.replace([np.inf, -np.inf], np.nan)
    
    # 8. OBV指标 (On Balance Volume) - 向量化重构
    diff = close.diff()
    direction = np.sign(diff).fillna(0)
    obv = (direction * volume).cumsum()
    obv_ma = obv.rolling(window=20).mean()
    
    # 9. DMI指标 (Directional Movement Index)
    # +DM和-DM
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm < 0] = 0
    
    # 处理正负DM
    plus_dm = pd.Series(np.where(plus_dm > minus_dm, plus_dm, 0), index=df.index)
    minus_dm = pd.Series(np.where(minus_dm > plus_dm, minus_dm, 0), index=df.index)
    
    # 真实波幅 TR = max(当日最高价-当日最低价, |当日最高价-昨日收盘价|, |当日最低价-昨日收盘价|)
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 14日平滑
    period = 14
    atr = tr.rolling(window=period).mean()
    plus_di = 100 * plus_dm.rolling(window=period).mean() / atr
    minus_di = 100 * minus_dm.rolling(window=period).mean() / atr
    
    # DX和ADX
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di) * 100).replace([np.inf, -np.inf], 0)
    adx = dx.rolling(window=period).mean()
    
    return {
        'volatility_ann': volatility,
        'max_drawdown': max_drawdown,
        'rsi': current_rsi,
        'macd': macd.iloc[-1],
        'macd_signal': signal.iloc[-1],
        'macd_hist': hist.iloc[-1],
        # 布林带
        'bb_upper': bb_upper.iloc[-1],
        'bb_middle': bb_middle.iloc[-1],
        'bb_lower': bb_lower.iloc[-1],
        'bb_width': bb_width.iloc[-1],
        'bb_percent': bb_percent.iloc[-1],
        # KDJ
        'kdj_k': k.iloc[-1],
        'kdj_d': d.iloc[-1],
        'kdj_j': j.iloc[-1],
        # CCI
        'cci': cci.iloc[-1],
        # OBV
        'obv': obv.iloc[-1],
        'obv_ma': obv_ma.iloc[-1],
        # DMI
        'dmi_plus_di': plus_di.iloc[-1] if not pd.isna(plus_di.iloc[-1]) else 0,
        'dmi_minus_di': minus_di.iloc[-1] if not pd.isna(minus_di.iloc[-1]) else 0,
        'dmi_adx': adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0,
    }


def calculate_all_indicators(df):
    """
    计算所有技术指标并添加到DataFrame
    返回包含所有指标列的DataFrame
    """
    if df.empty:
        return df
    
    df = df.copy()
    df = df.sort_values('日期')
    
    close = df['收盘']
    high = df['最高']
    low = df['最低']
    volume = df.get('成交量', pd.Series([0] * len(df), index=df.index))
    
    # RSI (14)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    # 布林带
    df['BB_Middle'] = close.rolling(window=20).mean()
    bb_std = close.rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + 2 * bb_std
    df['BB_Lower'] = df['BB_Middle'] - 2 * bb_std
    df['BB_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Middle'] * 100
    df['BB_Percent'] = (close - df['BB_Lower']) / (df['BB_Upper'] - df['BB_Lower']) * 100
    
    # KDJ
    n = 9
    low_n = low.rolling(window=n).min()
    high_n = high.rolling(window=n).max()
    rsv = (close - low_n) / (high_n - low_n) * 100
    rsv = rsv.fillna(50)
    df['KDJ_K'] = rsv.ewm(com=2, adjust=False).mean()
    df['KDJ_D'] = df['KDJ_K'].ewm(com=2, adjust=False).mean()
    df['KDJ_J'] = 3 * df['KDJ_K'] - 2 * df['KDJ_D']
    
    # CCI (20日)
    tp = (high + low + close) / 3
    tp_ma = tp.rolling(window=20).mean()
    tp_std = tp.rolling(window=20).std()
    df['CCI'] = (tp - tp_ma) / (0.015 * tp_std)
    df['CCI'] = df['CCI'].replace([np.inf, -np.inf], np.nan)
    
    # OBV - 向量化重构
    diff = close.diff()
    direction = np.sign(diff).fillna(0)
    df['OBV'] = (direction * volume).cumsum()
    df['OBV_MA'] = df['OBV'].rolling(window=20).mean()
    
    # DMI
    plus_dm = high.diff()
    minus_dm = low.diff().abs()
    plus_dm = pd.Series(np.where(plus_dm > minus_dm, plus_dm.where(plus_dm > 0, 0), 0), index=df.index)
    minus_dm = pd.Series(np.where(minus_dm > plus_dm, minus_dm.where(minus_dm > 0, 0), 0), index=df.index)
    
    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    period = 14
    atr = tr.rolling(window=period).mean()
    df['DMI_PlusDI'] = 100 * plus_dm.rolling(window=period).mean() / atr
    df['DMI_MinusDI'] = 100 * minus_dm.rolling(window=period).mean() / atr
    dx = (abs(df['DMI_PlusDI'] - df['DMI_MinusDI']) / (df['DMI_PlusDI'] + df['DMI_MinusDI']) * 100).replace([np.inf, -np.inf], 0)
    df['DMI_ADX'] = dx.rolling(window=period).mean()
    
    return df
