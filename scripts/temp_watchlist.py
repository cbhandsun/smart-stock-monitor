import akshare as ak
import json
from datetime import datetime

def get_watchlist_data():
    try:
        with open('/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json', 'r') as f:
            symbols = json.load(f)
        
        df_a = ak.stock_zh_a_spot()
        # Filter symbols. '代码' in akshare is usually like 'sh600000' or '000001'
        # Watchlist symbols are like "002428"
        # We need to match the numeric part.
        watchlist_df = df_a[df_a['代码'].str.endswith(tuple(symbols))]
        
        results = []
        for _, row in watchlist_df.iterrows():
            results.append({
                'name': row['名称'],
                'symbol': row['代码'],
                'price': float(row['最新价']),
                'change_pct': float(row['涨跌幅'])
            })
        return results
    except Exception as e:
        return str(e)

if __name__ == "__main__":
    data = get_watchlist_data()
    print(json.dumps(data, ensure_ascii=False))
