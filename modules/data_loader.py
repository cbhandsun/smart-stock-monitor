import akshare as ak
import pandas as pd
import requests
import os

# 代理处理
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

def fetch_kline(symbol):
    """
    使用新浪接口获取K线数据 (解决 akshare 在海外服务器被封锁的问题)
    symbol 格式: sh601318, sz002428
    """
    # 确保带上前缀
    if not symbol.startswith(('sh', 'sz')):
        symbol = "sh" + symbol if symbol.startswith('6') else "sz" + symbol
        
    url = f"http://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=240&ma=no&datalen=100"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json()
        if not data or not isinstance(data, list): 
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        # 统一列名以适配原有逻辑
        df.rename(columns={
            'day': '日期', 
            'open': '开盘', 
            'high': '最高', 
            'low': '最低', 
            'close': '收盘', 
            'volume': '成交量'
        }, inplace=True)
        
        # 转换数值类型
        for col in ['开盘', '最高', '最低', '收盘', '成交量']:
            df[col] = pd.to_numeric(df[col])
        
        # 计算均线
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        return df
    except Exception as e:
        print(f"Sina KLine fetch error for {symbol}: {e}")
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
        df = ak.stock_zyjs_report_em(symbol=code)
        if not df.empty:
            return df.head(3)
        return pd.DataFrame()
    except:
        return pd.DataFrame()
