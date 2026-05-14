import json
import os
from datetime import datetime

# Current target date based on available snapshot
TARGET_DATE = "2026-04-21"
SNAPSHOT_PATH = f"/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/cache/full_market_snapshot_{TARGET_DATE}.json"
WATCHLIST_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json"
OUTPUT_PATH = f"/home/node/.openclaw/workspace-dev/smart-stock-monitor/reports/daily/report_{TARGET_DATE}.json"

def run():
    print(f"[{datetime.now()}] Reading snapshot: {SNAPSHOT_PATH}")
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"Error: Snapshot {SNAPSHOT_PATH} not found.")
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
    
    # Market Indices Extraction (if possible from snapshot)
    # Most snapshots include indices or we can calculate market sentiment
    up_count = len([s for s in stocks if (s.get('涨跌幅') or 0) > 0])
    down_count = len([s for s in stocks if (s.get('涨跌幅') or 0) < 0])
    total_count = len(stocks)
    
    # Sort and get Value stocks (Lowest PB as proxy)
    valid_pb_stocks = [s for s in stocks if s.get('市净率') is not None]
    value_stocks = sorted(valid_pb_stocks, key=lambda x: x['市净率'])[:10]
    
    # Sort and get Momentum stocks (Highest 涨跌幅)
    valid_change_stocks = [s for s in stocks if s.get('涨跌幅') is not None]
    momentum_stocks = sorted(valid_change_stocks, key=lambda x: x['涨跌幅'], reverse=True)[:10]
    
    report = {
        "date": TARGET_DATE,
        "market_stats": {
            "上涨数": up_count,
            "下跌数": down_count,
            "平盘数": total_count - up_count - down_count,
            "涨跌比": round(up_count / max(down_count, 1), 2)
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
