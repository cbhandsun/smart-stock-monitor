import streamlit as st
import akshare as ak
import pandas as pd
from main import get_market_overview, get_hot_trend_stocks, find_value_stocks, get_trading_signals

st.set_page_config(page_title="Smart Stock Monitor", layout="wide")

st.title("📊 Smart Stock Monitor 智能看盘助手")
st.sidebar.info("这是一个基于 Python 和 AkShare 的智能股票监控工具。")

# 1. 大盘概况
st.header("📈 今日大盘趋势")
try:
    overview = get_market_overview()
    cols = st.columns(len(overview))
    for i, row in enumerate(overview.itertuples()):
        with cols[i]:
            change_color = "red" if row.涨跌幅 > 0 else "green"
            st.metric(
                label=row.名称, 
                value=f"{row.最新价:.2f}", 
                delta=f"{row.涨跌幅:.2f}%",
                delta_color="normal"
            )
except Exception as e:
    st.error(f"获取大盘数据失败: {e}")

# 2. 热门趋势选股 & 价值洼地
col_left, col_right = st.columns(2)

with col_left:
    st.header("🔥 热点趋势选股")
    sector_name, trend_stocks = get_hot_trend_stocks()
    if sector_name:
        st.subheader(f"当前最热板块: {sector_name}")
        if isinstance(trend_stocks, pd.DataFrame):
            st.dataframe(trend_stocks[['代码', '名称', '最新价', '涨跌幅', '成交量']], use_container_width=True)
    else:
        st.warning(trend_stocks)

with col_right:
    st.header("💎 价值洼地筛选")
    value = find_value_stocks()
    if isinstance(value, pd.DataFrame):
        st.subheader("低估值优质标的 (PE/PB 排序)")
        st.dataframe(value[['代码', '名称', '最新价', '市盈率-动态', '市净率']], use_container_width=True)
    else:
        st.warning(value)

# 3. 个股诊股
st.header("🔍 个股择时分析")
symbol = st.text_input("输入股票代码 (如 sh601318)", "sh601318")
if st.button("开始分析"):
    signal = get_trading_signals(symbol)
    if "买入" in signal:
        st.success(signal)
    elif "卖出" in signal:
        st.error(signal)
    else:
        st.info(signal)

st.divider()
st.caption("免责声明：本工具仅供学习交流，不构成投资建议。数据来源：AkShare")
