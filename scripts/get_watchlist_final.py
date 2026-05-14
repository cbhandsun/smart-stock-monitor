import akshare as ak
import json
import os

os.environ['HTTP_PROXY'] = ''
os.environ['HTTPS_PROXY'] = ''

watchlist_path = '/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json'
with open(watchlist_path, 'r') as f:
    codes = json.load(f)

df_a = ak.stock_zh_a_spot()
wl_df = df_a[df_a['代码'].str.contains('|'.join(codes))]

results = []
for _, row in wl_df.iterrows():
    results.append(f"{row['名称']} ({row['代码']}): {row['最新价']} ({row['涨跌幅']}%)")

print("\n".join(results))
