import os
# Clear proxy to fix EastMoney access issues (often blocked by proxy)
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY']:
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
            df = func(*args, **kwargs)
            if df is not None and not df.empty: return df
        except Exception as e:
            if i == 2: print(f"AKFetch Error: {e}")
            time.sleep(1.5)
    return pd.DataFrame()

@st.cache_data(ttl=300, show_spinner=False)
def get_market_overview():
    """
    Fetch market overview using Sina JS (more reliable than akshare EM in some networks)
    Fallback to akshare if Sina fails.
    """
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
                    name = parts[0]
                    price = float(parts[1])
                    change_pct = float(parts[3])
                    data.append({'名称': name, '最新价': price, '涨跌幅': change_pct})
        df = pd.DataFrame(data)
        if not df.empty: return df
    except: pass
    try:
        df = safe_ak_fetch(ak.stock_zh_index_spot_em)
        target_indices = ['上证指数', '深证成指', '创业板指']
        return df[df['名称'].isin(target_indices)]
    except: return pd.DataFrame(columns=['名称', '最新价', '涨跌幅'])

def get_full_market_data():
    """获取全市场快照，带多种源备选"""
    # 尝试 EM 源 (最快)
    df = safe_ak_fetch(ak.stock_zh_a_spot_em)
    if not df.empty: return df
    
    # 尝试腾讯源 (较快)
    try:
        df = ak.stock_zh_a_spot_config_sina() # 实际上 akshare 内部有多种实现
        # 如果还是不行，返回空
    except: pass
    
    return df

@st.cache_data(ttl=600, show_spinner=False)
def find_value_stocks(pe_max=15, pb_max=1.5):
    """【价值策略】低PE + 低PB"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        if '市盈率-动态' not in df.columns and '市盈率' in df.columns:
            df.rename(columns={'市盈率': '市盈率-动态'}, inplace=True)
        mask = (df['市盈率-动态'] > 0) & (df['市盈率-动态'] < pe_max) & (df['市净率'] > 0) & (df['市净率'] < pb_max)
        filtered = df[mask].copy()
        filtered['综合得分'] = (1 / filtered['市盈率-动态']) + (1 / filtered['市净率'])
        return filtered.sort_values(by='综合得分', ascending=False).head(10)[['代码', '名称', '最新价', '涨跌幅', '市盈率-动态', '市净率']]
    except: return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def find_momentum_stocks():
    """【动能策略】涨幅前列 + 换手活跃"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        # 筛选涨幅在 3% - 7% 之间，换手率 > 5% 的股票 (代表上升趋势且活跃)
        mask = (df['涨跌幅'] > 3) & (df['涨跌幅'] < 8) & (df['换手率'] > 5)
        filtered = df[mask].copy()
        return filtered.sort_values(by='成交额', ascending=False).head(10)[['代码', '名称', '最新价', '涨跌幅', '换手率', '成交额']]
    except: return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def find_growth_stocks():
    """【成长策略】大市值 + 稳健走势"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        # 简单模拟：市值较大且涨幅稳健的
        mask = (df['涨跌幅'] > 0) & (df['成交额'] > 1000000000) # 成交额 > 10亿
        filtered = df[mask].copy()
        return filtered.sort_values(by='涨跌幅', ascending=False).head(10)[['代码', '名称', '最新价', '涨跌幅', '成交额']]
    except: return pd.DataFrame()

def generate_ai_report(symbol, name, reports_df, signals):
    try:
        from ai_module import call_ai_for_stock_diagnosis
        import pandas as pd
        if not isinstance(reports_df, pd.DataFrame): reports_df = pd.DataFrame()
        ai_analysis = call_ai_for_stock_diagnosis(symbol, name, reports_df, signals)
        report = f"### 🤖 AI 深度诊断 ({name})\n\n{ai_analysis}\n\n> **⚠️ AI 提示**：此报告由 Gemini 大模型实时推理生成，仅供参考，不构成实质性投资建议。"
        return report
    except Exception as e: return f"AI 诊断模块加载失败: {e}"

def get_stock_names_batch(codes):
    if not codes: return {}
    sina_codes = []
    mapping = {}
    for c in codes:
        clean_c = c.strip()
        prefix = 's_sh' if clean_c.startswith('6') else 's_sz'
        sc = f"{prefix}{clean_c}"
        sina_codes.append(sc)
        mapping[sc] = c
    url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    name_map = {}
    try:
        r = requests.get(url, headers=headers, timeout=3)
        for line in r.text.split(';'):
            if '="' in line:
                val = line.split('="')[1].strip('\"').split(',')
                if len(val) > 0:
                    name = val[0]
                    for sc, orig in mapping.items():
                        if sc in line:
                            name_map[orig] = name
                            break
    except: pass
    return name_map

# 为了兼容 app.py 的旧调用
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
