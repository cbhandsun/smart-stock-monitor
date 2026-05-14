import json
import os
from datetime import datetime

# Today's date from the environment/system
today_str = "2026-05-04"

# Define paths
SNAPSHOT_PATH = f"/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/cache/full_market_snapshot_{today_str}.json"
WATCHLIST_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json"
OUTPUT_PATH = f"/home/node/.openclaw/workspace-dev/smart-stock-monitor/reports/daily/report_{today_str}.json"

def run():
    print(f"[{datetime.now()}] Reading snapshot: {SNAPSHOT_PATH}")
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"Error: Snapshot {SNAPSHOT_PATH} not found.")
        return

    with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
        stocks = json.load(f)

    # Load Watchlist codes
    watchlist_codes = []
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            watchlist_codes = json.load(f)
    
    # Filter Watchlist Stocks
    # Standardize codes if needed (some are sh600000, some 600000)
    def clean_code(c):
        return c.replace('sh', '').replace('sz', '')
    
    clean_wl_codes = [clean_code(c) for c in watchlist_codes]
    watchlist_data = [s for s in stocks if clean_code(s.get('代码', '')) in clean_wl_codes]
    
    # Sort and get Value stocks (Lowest PB as proxy)
    # The snapshot keys might be different. Let's check a few keys.
    # In Sina spot: '代码', '名称', '最新价', '涨跌幅', '市盈率', '市净率'
    valid_pb_stocks = [s for s in stocks if s.get('市净率') is not None and s.get('市净率') > 0]
    value_stocks = sorted(valid_pb_stocks, key=lambda x: x['市净率'])[:10]
    
    # Sort and get Momentum stocks (Highest 涨跌幅)
    valid_change_stocks = [s for s in stocks if s.get('涨跌幅') is not None]
    momentum_stocks = sorted(valid_change_stocks, key=lambda x: x['涨跌幅'], reverse=True)[:10]
    
    # Calculate market summary
    all_changes = [s.get('涨跌幅') for s in stocks if s.get('涨跌幅') is not None]
    avg_change = sum(all_changes) / len(all_changes) if all_changes else 0
    
    # Count up/down
    up_count = len([c for c in all_changes if c > 0])
    down_count = len([c for c in all_changes if c < 0])
    flat_count = len([c for c in all_changes if c == 0])

    report = {
        "date": today_str,
        "market_summary": {
            "average_change": round(avg_change, 2),
            "total_stocks": len(stocks),
            "up_count": up_count,
            "down_count": down_count,
            "flat_count": flat_count
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
