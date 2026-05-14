import json
import os
import pandas as pd
from datetime import datetime

# Define paths
SNAPSHOT_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/cache/full_market_snapshot_2026-04-16.json"
WATCHLIST_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json"
OUTPUT_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/reports/daily/report_2026-04-16.json"

def run():
    print(f"[{datetime.now()}] Reading snapshot: {SNAPSHOT_PATH}")
    if not os.path.exists(SNAPSHOT_PATH):
        print("Error: Snapshot not found.")
        return

    with open(SNAPSHOT_PATH, 'r') as f:
        data = json.load(f)

    df = pd.DataFrame(data)
    
    # Load Watchlist
    watchlist = []
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'r') as f:
            watchlist = json.load(f)
    
    # Filter Watchlist Stocks
    watchlist_data = df[df['代码'].isin(watchlist)].copy()
    
    # Sort and get Value stocks (Lowest PB/PE as proxy)
    value_stocks = df.dropna(subset=['市盈率', '市净率']).sort_values('市净率').head(10).copy()
    
    # Sort and get Momentum stocks (Highest 涨跌幅)
    momentum_stocks = df.sort_values('涨跌幅', ascending=False).head(10).copy()
    
    # Placeholder for Indices (since they aren't in the snapshot file)
    # Using previous report structure
    report = {
        "date": datetime.now().isoformat(),
        "market_overview": {
            "名称": {"0": "上证指数", "1": "深证成指", "2": "创业板指"},
            "最新价": {"0": "3xxx.xx", "1": "1xxxx.xx", "2": "2xxx.xx"},
            "涨跌幅": {"0": "TBD", "1": "TBD", "2": "TBD"}
        },
        "watchlist_performance": watchlist_data.to_dict(),
        "value_stocks": value_stocks.to_dict(),
        "momentum_stocks": momentum_stocks.to_dict()
    }
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"[{datetime.now()}] Report generated: {OUTPUT_PATH}")

if __name__ == "__main__":
    run()
