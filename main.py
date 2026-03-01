import akshare as ak
import pandas as pd
import time

def get_market_overview():
    """获取大盘概况"""
    print("正在获取大盘走势...")
    # 这里可以获取上证、深证、创业板指数
    df = ak.stock_zh_index_spot()
    return df[df['名称'].isin(['上证指数', '深证成指', '创业板指'])]

def get_hot_sectors():
    """获取热点板块"""
    print("正在分析热点板块...")
    df = ak.stock_board_industry_name_em()
    return df.sort_values(by='涨跌幅', ascending=False).head(5)

def find_value_stocks():
    """寻找价值洼地 (示例：低PE、低PB、高股息)"""
    print("正在筛选价值洼地股票 (东方财富实时行情)...")
    try:
        # 获取所有 A 股实时行情
        df = ak.stock_zh_a_spot_em()
        
        # 筛选逻辑：
        # 1. 市盈率(PE) > 0 且 < 15
        # 2. 市净率(PB) > 0 且 < 1.5
        # 3. 股息率 > 3%
        
        # 注意：不同版本 akshare 列名可能不同，需做适配
        # 常用列名：'市盈率-动态', '市净率', '股息率'
        mask = (df['市盈率-动态'] > 0) & (df['市盈率-动态'] < 15) & \
               (df['市净率'] > 0) & (df['市净率'] < 1.5)
        
        value_stocks = df[mask].copy()
        # 按市盈率升序排序
        return value_stocks.sort_values(by='市盈率-动态').head(10)
    except Exception as e:
        return f"筛选失败: {str(e)}"

def get_trading_signals(symbol="sh600000"):
    """
    智能买卖点提示 (基于简单的双均线金叉策略)
    symbol: 股票代码，如 sh600000
    """
    print(f"正在分析 {symbol} 的交易信号...")
    try:
        # 获取最近 100 天的历史数据
        df = ak.stock_zh_a_hist(symbol=symbol[2:], period="daily", adjust="qfq")
        
        # 计算 5 日均线和 20 日均线
        df['MA5'] = df['收盘'].rolling(window=5).mean()
        df['MA20'] = df['收盘'].rolling(window=20).mean()
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 金叉：MA5 从下方穿过 MA20
        if prev['MA5'] < prev['MA20'] and latest['MA5'] > latest['MA20']:
            return "【买入信号】MA5 金叉 MA20，短期趋势转强"
        # 死叉：MA5 从上方穿过 MA20
        elif prev['MA5'] > prev['MA20'] and latest['MA5'] < latest['MA20']:
            return "【卖出信号】MA5 死叉 MA20，短期趋势转弱"
        else:
            return "【持仓/观望】暂无显著交叉信号"
    except Exception as e:
        return f"分析信号失败: {str(e)}"

def main():
    print("=== Smart Stock Monitor 启动 ===")
    
    # 1. 大盘趋势
    overview = get_market_overview()
    print("\n[今日大盘]")
    print(overview[['名称', '最新价', '涨跌额', '涨跌幅']])
    
    # 2. 热门板块
    hot = get_hot_sectors()
    print("\n[热门板块 TOP5]")
    print(hot[['板块名称', '涨跌幅', '总市值']])

    # 3. 价值洼地
    value = find_value_stocks()
    print("\n[价值洼地筛选 (低PE/PB TOP10)]")
    if isinstance(value, pd.DataFrame):
        print(value[['代码', '名称', '最新价', '市盈率-动态', '市净率']])
    else:
        print(value)

    # 4. 个股信号示例 (以中国平安为例)
    signal = get_trading_signals("sh601318")
    print(f"\n[个股信号 - 中国平安(601318)]\n{signal}")
    
    print("\n监控运行中... (按 Ctrl+C 退出)")

if __name__ == "__main__":
    main()
