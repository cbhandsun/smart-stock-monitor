import akshare as ak
import json
import os

watchlist_path = '/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json'
with open(watchlist_path, 'r') as f:
    codes = json.load(f)

df_a = ak.stock_zh_a_spot_em()
# EM codes are like SH600000 or SZ000001 usually, butsina/em spot might vary
# EM spot columns: 代码, 名称, 最新价, 涨跌幅
wl_df = df_a[df_a['代码'].isin(codes)]

results = []
for _, row in wl_df.iterrows():
    results.append(f"{row['名称']} ({row['代码']}): {row['最新价']} ({row['涨跌幅']}%)")

print("\n".join(results))
