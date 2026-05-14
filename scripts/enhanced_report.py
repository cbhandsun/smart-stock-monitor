import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime

# Disable proxy to avoid connection issues
os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

def generate_enhanced_report():
    print(f"[{datetime.now()}] 正在生成深度复盘研报...")
    
    report = {}
    
    # 1. 大盘表现
    try:
        df_index = ak.stock_zh_index_spot_sina()
        indices = df_index[df_index['名称'].isin(['上证指数', '深证成指', '创业板指'])]
        report['index'] = []
        for _, row in indices.iterrows():
            price = float(row['最新价'])
            prev_close = float(row['昨收'])
            change_pct = (price - prev_close) / prev_close * 100
            report['index'].append({
                'name': row['名称'],
                'price': price,
                'change': change_pct
            })
    except Exception as e:
        report['index_error'] = str(e)

    # 2. 自选股表现
    try:
        watchlist_path = '/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json'
        if os.path.exists(watchlist_path):
            with open(watchlist_path, 'r') as f:
                codes = json.load(f)
            df_a = ak.stock_zh_a_spot()
            # Handle different code formats in watchlist vs akshare
            wl_df = df_a[df_a['代码'].apply(lambda x: any(c in x for c in codes))]
            report['watchlist'] = []
            for _, row in wl_df.iterrows():
                report['watchlist'].append({
                    'name': row['名称'],
                    'code': row['代码'],
                    'price': row['最新价'],
                    'change': row['涨跌幅']
                })
    except Exception as e:
        report['watchlist_error'] = str(e)

    # 3. 热点板块
    try:
        # Using a more stable sector flow data if possible
        sector_flow = ak.stock_board_industry_name_em() # List industries
        # Just getting some sectors and their performance for now if flow fails
        # Or try the flow one again without proxy
        sector_flow = ak.stock_sector_fund_flow_rank()
        top_sectors = sector_flow.sort_values(by='今日主力净额', ascending=False).head(5)
        report['sectors'] = []
        for _, row in top_sectors.iterrows():
            report['sectors'].append({
                'name': row['板块名称'],
                'flow': row['今日主力净额'] / 100000000,
                'change': row['涨跌幅']
            })
    except Exception as e:
        report['sectors_error'] = str(e)

    # 4. 价值选股
    try:
        df_a = ak.stock_zh_a_spot()
        # Use available columns
        # print(df_a.columns) # For debugging
        # Typical columns: 代码, 名称, 最新价, 涨跌幅, 买入, 卖出, 昨收, 今开, 最高, 最低, 成交量, 成交额, per, pb, mktcap, nmc
        # The KeyError 'mktcap' might be because it's named differently or missing.
        # Let's try to detect column names.
        pe_col = 'per' if 'per' in df_a.columns else None
        pb_col = 'pb' if 'pb' in df_a.columns else None
        
        if pe_col and pb_col:
            df_a[pe_col] = pd.to_numeric(df_a[pe_col], errors='coerce')
            df_a[pb_col] = pd.to_numeric(df_a[pb_col], errors='coerce')
            mask = (df_a[pe_col] > 0) & (df_a[pe_col] < 15) & (df_a[pb_col] > 0) & (df_a[pb_col] < 1.5)
            value_stocks = df_a[mask].sort_values(by=pe_col).head(5)
            report['value_stocks'] = []
            for _, row in value_stocks.iterrows():
                report['value_stocks'].append({
                    'name': row['名称'],
                    'code': row['代码'],
                    'pe': row[pe_col],
                    'pb': row[pb_col]
                })
    except Exception as e:
        report['value_error'] = str(e)

    return report

if __name__ == "__main__":
    data = generate_enhanced_report()
    print(json.dumps(data, ensure_ascii=False, indent=2))
