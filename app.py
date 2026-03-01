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

import plotly.graph_objects as go

def plot_radar_chart(scores, categories):
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=scores,
        theta=categories,
        fill='toself',
        name='综合评估'
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        ),
        showlegend=False,
        title="个股综合评估雷达图"
    )
    return fig

# 3. 个股诊股
st.header("🔍 个股综合评估雷达")
symbol_input = st.text_input("输入股票代码进行全方位诊断 (如 sh601318)", "sh601318")
if st.button("开始全面诊断"):
    with st.spinner('正在调取深度数据...'):
        # 模拟多维度评分逻辑（实际可接入财务、技术、资金面计算）
        # 维度：估值(PE/PB)、动能(MA)、资金(Flow)、成长(Growth)、红利(Dividend)
        categories = ['估值安全度', '技术动能', '主力资金', '成长潜力', '股息红利']
        
        # 示例评分逻辑 (实际应根据数据计算)
        scores = [85, 60, 45, 70, 90] # 以中国平安为例的示意评分
        
        fig = plot_radar_chart(scores, categories)
        st.plotly_chart(fig, use_container_width=True)
        
        signal = get_trading_signals(symbol_input)
        st.info(f"实时信号：{signal}")

st.divider()
st.caption("免责声明：本工具仅供学习交流，不构成投资建议。数据来源：AkShare")
