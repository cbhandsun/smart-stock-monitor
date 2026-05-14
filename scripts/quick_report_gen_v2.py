import json
import os
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

    with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
        stocks = json.load(f)

    # Load Watchlist
    watchlist_codes = []
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'r') as f:
            watchlist_codes = json.load(f)
    
    # Filter Watchlist Stocks
    watchlist_data = [s for s in stocks if s.get('代码') in watchlist_codes]
    
    # Sort and get Value stocks (Lowest PB as proxy)
    # Filter out None values first
    valid_pb_stocks = [s for s in stocks if s.get('市净率') is not None]
    value_stocks = sorted(valid_pb_stocks, key=lambda x: x['市净率'])[:10]
    
    # Sort and get Momentum stocks (Highest 涨跌幅)
    valid_change_stocks = [s for s in stocks if s.get('涨跌幅') is not None]
    momentum_stocks = sorted(valid_change_stocks, key=lambda x: x['涨跌幅'], reverse=True)[:10]
    
    report = {
        "date": datetime.now().isoformat(),
        "market_overview": {
            "名称": {"0": "上证指数", "1": "深证成指", "2": "创业板指"},
            "最新价": {"0": "N/A", "1": "N/A", "2": "N/A"},
            "涨跌幅": {"0": "N/A", "1": "N/A", "2": "N/A"}
        },
        "watchlist": watchlist_data,
        "value_stocks": value_stocks,
        "momentum_stocks": momentum_stocks
    }
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"[{datetime.now()}] Report generated: {OUTPUT_PATH}")

if __name__ == "__main__":
    run()
