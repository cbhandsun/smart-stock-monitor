import os
# Clear proxy to fix EastMoney access issues (often blocked by proxy)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'ALL_PROXY', 'http_proxy'.upper(), 'https_proxy'.upper(), 'all_proxy'.upper()]:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

import akshare as ak
import pandas as pd
import streamlit as st
import requests
import time

def safe_ak_fetch(func, *args, **kwargs):
    """带重试的 akshare 数据抓取"""
    for i in range(3):
        try:
            # 强制不使用代理
            df = func(*args, **kwargs)
            if df is not None and not df.empty: return df
        except Exception as e:
            if i == 2: print(f"AKFetch Final Error: {e}")
            time.sleep(2)
    return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_market_overview():
    """新浪接口获取指数快照"""
    try:
        url = "https://hq.sinajs.cn/list=s_sh000001,s_sz399001,s_sz399006"
        headers = {'Referer': 'https://finance.sina.com.cn/'}
        resp = requests.get(url, headers=headers, timeout=5)
        text = resp.text
        data = []
        for line in text.strip().split(';'):
            if '="' in line:
                key, val = line.split('="')
                val = val.strip('"')
                parts = val.split(',')
                if len(parts) > 3:
                    data.append({'名称': parts[0], '最新价': float(parts[1]), '涨跌幅': float(parts[3])})
        df = pd.DataFrame(data)
        if not df.empty: return df
    except: pass
    return pd.DataFrame(columns=['名称', '最新价', '涨跌幅'])

def get_full_market_data():
    """抓取全市场快照，针对 empty 情况增加强制刷新逻辑"""
    # 优先尝试 EM 源
    df = safe_ak_fetch(ak.stock_zh_a_spot_em)
    
    # 如果 EM 依然为空，说明该接口被当前环境屏蔽，尝试腾讯接口作为终极兜底
    if df.empty:
        try:
            df = ak.stock_zh_a_spot_config_sina() # 注意：某些版本 akshare 腾讯接口函数名不同
        except:
            # 实在不行尝试历史行情接口凑合今天的数据
            pass
    return df

@st.cache_data(ttl=600, show_spinner=False)
def find_value_stocks(pe_max=20, pb_max=2.0):
    """价值挖掘逻辑优化"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    
    try:
        # 兼容不同列名
        pe_col = '市盈率-动态' if '市盈率-动态' in df.columns else '市盈率'
        pb_col = '市净率'
        
        # 转换数据类型确保万无一失
        df[pe_col] = pd.to_numeric(df[pe_col], errors='coerce')
        df[pb_col] = pd.to_numeric(df[pb_col], errors='coerce')
        
        mask = (df[pe_col] > 0) & (df[pe_col] < pe_max) & (df[pb_col] > 0) & (df[pb_col] < pb_max)
        filtered = df[mask].copy()
        
        # 计算综合价值得分
        filtered['综合得分'] = (1 / filtered[pe_col]) + (1 / filtered[pb_col])
        res = filtered.sort_values(by='综合得分', ascending=False).head(15)
        return res[['代码', '名称', '最新价', '涨跌幅', pe_col, pb_col]].rename(columns={pe_col: 'PE', pb_col: 'PB'})
    except: return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def find_momentum_stocks():
    """动能策略逻辑优化"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
        df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce')
        mask = (df['涨跌幅'] > 2) & (df['涨跌幅'] < 9) & (df['换手率'] > 3)
        filtered = df[mask].copy()
        return filtered.sort_values(by='成交额', ascending=False).head(15)[['代码', '名称', '最新价', '涨跌幅', '换手率', '成交额']]
    except: return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def find_growth_stocks():
    """成长策略逻辑优化"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
        # 筛选成交活跃（>5亿）且表现正向的标的
        mask = (df['涨跌幅'] > 0) & (df['成交额'] > 500000000)
        filtered = df[mask].copy()
        return filtered.sort_values(by='涨跌幅', ascending=False).head(15)[['代码', '名称', '最新价', '涨跌幅', '成交额']]
    except: return pd.DataFrame()

# ---- 其余辅助函数保持不变 ----
def generate_ai_report(symbol, name, reports_df, signals):
    try:
        from ai_module import call_ai_for_stock_diagnosis
        if not isinstance(reports_df, pd.DataFrame): reports_df = pd.DataFrame()
        ai_analysis = call_ai_for_stock_diagnosis(symbol, name, reports_df, signals)
        return f"### 🤖 AI 深度诊断 ({name})\n\n{ai_analysis}\n\n> **⚠️ AI 提示**：此报告由 Gemini 大模型实时推理生成，仅供参考。"
    except Exception as e: return f"AI 诊断模块加载失败: {e}"

def get_stock_names_batch(codes):
    if not codes: return {}
    sina_codes = [f"{'s_sh' if c.strip().startswith('6') else 's_sz'}{c.strip()}" for c in codes]
    mapping = {f"{'s_sh' if c.strip().startswith('6') else 's_sz'}{c.strip()}": c.strip() for c in codes}
    url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    name_map = {}
    try:
        r = requests.get(url, headers=headers, timeout=3)
        for line in r.text.split(';'):
            if '="' in line:
                key = line.split('=')[0].split('_')[-1]
                name = line.split('="')[1].split(',')[0]
                # 模糊匹配映射
                for k, v in mapping.items():
                    if k.endswith(key): name_map[v] = name
    except: pass
    return name_map

def get_stock_research_reports(symbol):
    try: return ak.stock_zyjs_report_em(symbol=symbol).head(3)
    except: return pd.DataFrame()

def get_profit_forecast(symbol):
    try: return ak.stock_profit_forecast_em(symbol=symbol).head(1)
    except: return pd.DataFrame()

def get_trading_signals(symbol):
    from modules.data_loader import fetch_trading_signals
    return fetch_trading_signals(symbol)

def get_stock_kline_data(symbol):
    from modules.data_loader import fetch_kline
    return fetch_kline(symbol)

def get_hot_trend_stocks():
    try:
        sector_flow = ak.stock_sector_fund_flow_rank(indicator="今日")
        if sector_flow.empty: return "数据暂缺", pd.DataFrame()
        top_sector = sector_flow.sort_values(by='主力净流入-净额', ascending=False).iloc[0]
        sector_name = top_sector['名称']
        try:
            stocks_in_sector = ak.stock_board_industry_cons_em(symbol=sector_name)
            trend_stocks = stocks_in_sector[stocks_in_sector['涨跌幅'] > 2].sort_values(by='涨跌幅', ascending=False)
            return sector_name, trend_stocks.head(5)
        except: return sector_name, pd.DataFrame()
    except: return "未知板块", pd.DataFrame()
