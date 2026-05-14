import json
import os
from datetime import datetime

# Define paths
TODAY_STR = datetime.now().strftime("%Y-%m-%d")
SNAPSHOT_PATH = f"/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/cache/full_market_snapshot_{TODAY_STR}.json"
WATCHLIST_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json"
OUTPUT_PATH = f"/home/node/.openclaw/workspace-dev/smart-stock-monitor/reports/daily/report_{TODAY_STR}.json"

def run():
    print(f"[{datetime.now()}] Reading snapshot: {SNAPSHOT_PATH}")
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"Error: Snapshot not found at {SNAPSHOT_PATH}")
        return

    try:
        with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
            stocks = json.load(f)
    except Exception as e:
        print(f"Error reading snapshot: {e}")
        return

    # Load Watchlist
    watchlist_codes = []
    if os.path.exists(WATCHLIST_PATH):
        try:
            with open(WATCHLIST_PATH, 'r') as f:
                watchlist_codes = json.load(f)
        except Exception as e:
            print(f"Error reading watchlist: {e}")
    
    # Filter Watchlist Stocks
    watchlist_data = [s for s in stocks if s.get('代码') in watchlist_codes]
    
    # Market Overview (Simplified since we don't have direct index values in the simple snapshot)
    # We can calculate average market performance from all stocks
    valid_changes = [s.get('涨跌幅') for s in stocks if s.get('涨跌幅') is not None]
    avg_change = sum(valid_changes) / len(valid_changes) if valid_changes else 0
    
    # Sort and get Value stocks (Lowest PB as proxy)
    valid_pb_stocks = [s for s in stocks if s.get('市净率') is not None and s.get('市净率') > 0]
    value_stocks = sorted(valid_pb_stocks, key=lambda x: x['市净率'])[:10]
    
    # Sort and get Momentum stocks (Highest 涨跌幅)
    valid_change_stocks = [s for s in stocks if s.get('涨跌幅') is not None]
    momentum_stocks = sorted(valid_change_stocks, key=lambda x: x['涨跌幅'], reverse=True)[:10]
    
    report = {
        "date": datetime.now().isoformat(),
        "market_summary": {
            "average_change": round(avg_change, 2),
            "total_stocks": len(stocks)
        },
        "watchlist": watchlist_data,
        "top_value": value_stocks,
        "top_momentum": momentum_stocks
    }
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"[{datetime.now()}] Report generated: {OUTPUT_PATH}")

if __name__ == "__main__":
    run()
