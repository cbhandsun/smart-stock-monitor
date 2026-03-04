import os
# Clear proxy to fix access issues
for k in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'ALL_PROXY', 'http_proxy'.upper(), 'https_proxy'.upper(), 'all_proxy'.upper()]:
    os.environ.pop(k, None)
os.environ['NO_PROXY'] = '*'

import akshare as ak
import pandas as pd
import streamlit as st
import requests
import time
import re

def fetch_sina_market_snapshot(page=1):
    """通过新浪财经接口抓取全市场快照 (作为 AkShare 失效时的备选)"""
    # 新浪 A 股行情列表接口 (每页 80 条)
    url = f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=80&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=init"
    try:
        r = requests.get(url, timeout=5)
        # 新浪返回的是不规范的 JSON (key 没有引号)，需要处理
        text = r.text
        # 简单转换：给 key 加引号
        text = re.sub(r'([\{,])(\w+):', r'\1"\2":', text)
        import json
        data = json.loads(text)
        df = pd.DataFrame(data)
        if not df.empty:
            # 统一列名以兼容后续逻辑
            df.rename(columns={
                'symbol': '代码',
                'name': '名称',
                'trade': '最新价',
                'changepercent': '涨跌幅',
                'per': '市盈率',
                'pb': '市净率',
                'amount': '成交额',
                'turnoverratio': '换手率'
            }, inplace=True)
            # 处理代码格式 (sh600519 -> 600519)
            df['代码'] = df['代码'].apply(lambda x: x[2:] if len(x) > 2 else x)
            return df
    except Exception as e:
        print(f"Sina Fetch Error: {e}")
    return pd.DataFrame()

def get_full_market_data():
    """抓取全市场快照，针对海外服务器增加新浪源兜底"""
    # 1. 尝试 EM 源 (AkShare)
    df = pd.DataFrame()
    try:
        # 减少抓取量尝试通过
        df = ak.stock_zh_a_spot_em()
    except: pass
    
    # 2. 如果 EM 依然失败，使用新浪接口手动抓取前几页做演示
    if df.empty:
        pages = []
        for p in range(1, 4): # 抓取前 3 页 (240 只股票)
            pdf = fetch_sina_market_snapshot(page=p)
            if not pdf.empty: pages.append(pdf)
            time.sleep(0.5)
        if pages:
            df = pd.concat(pages, ignore_index=True)
            
    return df

@st.cache_data(ttl=600, show_spinner=False)
def find_value_stocks(pe_max=25, pb_max=2.5):
    """价值挖掘逻辑 (兼容新浪源)"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    
    try:
        pe_col = '市盈率' if '市盈率' in df.columns else '市盈率-动态'
        pb_col = '市净率'
        
        df[pe_col] = pd.to_numeric(df[pe_col], errors='coerce')
        df[pb_col] = pd.to_numeric(df[pb_col], errors='coerce')
        df['最新价'] = pd.to_numeric(df['最新价'], errors='coerce')
        df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
        
        mask = (df[pe_col] > 0) & (df[pe_col] < pe_max) & (df[pb_col] > 0) & (df[pb_col] < pb_max)
        filtered = df[mask].copy()
        filtered['综合得分'] = (1 / filtered[pe_col]) + (1 / filtered[pb_col])
        res = filtered.sort_values(by='综合得分', ascending=False).head(15)
        return res[['代码', '名称', '最新价', '涨跌幅', pe_col, pb_col]].rename(columns={pe_col: 'PE', pb_col: 'PB'})
    except: return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def find_momentum_stocks():
    """动能策略 (兼容新浪源)"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
        df['换手率'] = pd.to_numeric(df['换手率'], errors='coerce')
        mask = (df['涨跌幅'] > 1) & (df['涨跌幅'] < 9)
        filtered = df[mask].copy()
        return filtered.sort_values(by='涨跌幅', ascending=False).head(15)[['代码', '名称', '最新价', '涨跌幅', '成交额']]
    except: return pd.DataFrame()

@st.cache_data(ttl=600, show_spinner=False)
def find_growth_stocks():
    """成长策略 (兼容新浪源)"""
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
        mask = (df['成交额'] > 100000000) # > 1亿
        filtered = df[mask].copy()
        return filtered.sort_values(by='成交额', ascending=False).head(15)[['代码', '名称', '最新价', '涨跌幅', '成交额']]
    except: return pd.DataFrame()

# ---- 后续 AI 诊断及名称获取函数保持不变 (它们已经使用新浪源了) ----
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
    url = f"https://hq.sinajs.cn/list={','.join(sina_codes)}"
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    name_map = {}
    try:
        r = requests.get(url, headers=headers, timeout=3)
        for line in r.text.split(';'):
            if '="' in line:
                key = line.split('=')[0].split('_')[-1]
                name = line.split('="')[1].split(',')[0]
                for c in codes:
                    if c.strip() in key: name_map[c.strip()] = name
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
