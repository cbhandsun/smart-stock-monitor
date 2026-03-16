import os
import logging
import glob
import akshare as ak
import pandas as pd
import streamlit as st
import requests
import time
import re
import datetime
import json
from modules.data_loader import fetch_trading_signals, fetch_kline

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def cleanup_old_cache(max_age_days=7):
    """清理过期缓存文件"""
    now = time.time()
    removed = 0
    for f in glob.glob(os.path.join(CACHE_DIR, "*.json")):
        if now - os.path.getmtime(f) > max_age_days * 86400:
            try:
                os.remove(f)
                removed += 1
            except OSError as e:
                logger.warning(f"清理缓存文件失败 {f}: {e}")
    if removed:
        logger.info(f"已清理 {removed} 个过期缓存文件")

# 启动时自动清理过期缓存
cleanup_old_cache()

def get_cache_path(key):
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(CACHE_DIR, f"{key}_{date_str}.json")

def load_from_cache(key):
    path = get_cache_path(key)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                data = json.load(f)
                return pd.DataFrame(data)
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning(f"缓存读取失败 {path}: {e}")
    return None

def save_to_cache(key, df):
    if df is None or df.empty: return
    path = get_cache_path(key)
    try:
        # Convert to records to avoid orientation issues
        df.to_json(path, orient='records', force_ascii=False)
    except Exception as e:
        logger.warning(f"缓存写入失败 {path}: {e}")

@st.cache_data(ttl=300, show_spinner=False)
def get_market_overview():
    """获取市场指数概览 (新浪源)"""
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
    except Exception as e:
        logger.warning(f"获取市场概览失败: {e}")
    return pd.DataFrame(columns=['名称', '最新价', '涨跌幅'])

def fetch_sina_market_snapshot(page=1):
    """通过新浪财经接口抓取全市场快照 (作为 AkShare 失效时的备选)"""
    url = f"https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page={page}&num=80&sort=changepercent&asc=0&node=hs_a&symbol=&_s_r_a=init"
    try:
        r = requests.get(url, timeout=5)
        text = r.text
        text = re.sub(r'([\{,])(\w+):', r'\1"\2":', text)
        # json 已在文件顶部导入
        data = json.loads(text)
        df = pd.DataFrame(data)
        if not df.empty:
            df.rename(columns={
                'symbol': '代码', 'name': '名称', 'trade': '最新价',
                'changepercent': '涨跌幅', 'per': '市盈率', 'pb': '市净率',
                'amount': '成交额', 'turnoverratio': '换手率'
            }, inplace=True)
            df['代码'] = df['代码'].apply(lambda x: x[2:] if len(x) > 2 else x)
            return df
    except Exception as e:
        print(f"Sina Fetch Error: {e}")
    return pd.DataFrame()

def get_full_market_data():
    """抓取全市场快照 (优先从当日缓存读取)"""
    cache_key = "full_market_snapshot"
    cached_df = load_from_cache(cache_key)
    if cached_df is not None:
        return cached_df

    df = pd.DataFrame()
    # 尝试 EM 源 (AkShare)
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        logger.warning(f"AkShare 全市场快照获取失败: {e}")
    
    # 如果 EM 依然失败，使用新浪接口兜底
    if df.empty:
        pages = []
        for p in range(1, 4):
            pdf = fetch_sina_market_snapshot(page=p)
            if not pdf.empty: pages.append(pdf)
            time.sleep(0.5)
        if pages:
            df = pd.concat(pages, ignore_index=True)
    
    if not df.empty:
        save_to_cache(cache_key, df)
    return df

@st.cache_data(ttl=86400, show_spinner=False) # Streamlit cache extended to 24h
def find_value_stocks(pe_max=25, pb_max=2.5):
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
    except Exception as e:
        logger.warning(f"价值股筛选失败: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=86400, show_spinner=False)
def find_momentum_stocks():
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        df['涨跌幅'] = pd.to_numeric(df['涨跌幅'], errors='coerce')
        mask = (df['涨跌幅'] > 1) & (df['涨跌幅'] < 9)
        filtered = df[mask].copy()
        return filtered.sort_values(by='涨跌幅', ascending=False).head(15)[['代码', '名称', '最新价', '涨跌幅', '成交额']]
    except Exception as e:
        logger.warning(f"动量股筛选失败: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=86400, show_spinner=False)
def find_growth_stocks():
    df = get_full_market_data()
    if df.empty: return pd.DataFrame()
    try:
        df['成交额'] = pd.to_numeric(df['成交额'], errors='coerce')
        mask = (df['成交额'] > 100000000)
        filtered = df[mask].copy()
        return filtered.sort_values(by='成交额', ascending=False).head(15)[['代码', '名称', '最新价', '涨跌幅', '成交额']]
    except Exception as e:
        logger.warning(f"成长股筛选失败: {e}")
        return pd.DataFrame()

def generate_ai_report(symbol, name, reports_df, signals):
    try:
        from core.ai_client import call_ai_for_stock_diagnosis
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
    except Exception as e:
        logger.warning(f"批量获取股票名称失败: {e}")
    return name_map

def get_stock_research_reports(symbol):
    try:
        return ak.stock_zyjs_report_em(symbol=symbol).head(3)
    except Exception as e:
        logger.warning(f"获取研报失败 {symbol}: {e}")
        return pd.DataFrame()

def get_profit_forecast(symbol):
    try:
        return ak.stock_profit_forecast_em(symbol=symbol).head(1)
    except Exception as e:
        logger.warning(f"获取盈利预测失败 {symbol}: {e}")
        return pd.DataFrame()

def get_trading_signals(symbol):
    return fetch_trading_signals(symbol)

def get_stock_kline_data(symbol):
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
        except Exception as e:
            logger.warning(f"获取板块成分股失败 {sector_name}: {e}")
            return sector_name, pd.DataFrame()
    except Exception as e:
        logger.warning(f"获取板块资金流向失败: {e}")
        return "未知板块", pd.DataFrame()
