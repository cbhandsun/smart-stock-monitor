import json
import os
from datetime import datetime

# Today is 2026-04-28
today_str = "2026-04-28"
ROOT_DIR = "/home/node/.openclaw/workspace-dev/smart-stock-monitor"
SNAPSHOT_PATH = f"{ROOT_DIR}/data/cache/full_market_snapshot_{today_str}.json"
WATCHLIST_PATH = f"{ROOT_DIR}/data/watchlist.json"

def run():
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"Error: Snapshot {SNAPSHOT_PATH} not found.")
        return

    with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
        stocks = json.load(f)

    # Load Watchlist
    watchlist_codes = []
    if os.path.exists(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            watchlist_codes = json.load(f)
    
    # Filter Watchlist
    watchlist_data = [s for s in stocks if s.get('代码') in watchlist_codes]
    
    # Market Summary
    all_changes = [s.get('涨跌幅') for s in stocks if s.get('涨跌幅') is not None]
    avg_change = sum(all_changes) / len(all_changes) if all_changes else 0
    up_count = len([c for c in all_changes if c > 0])
    down_count = len([c for c in all_changes if c < 0])
    flat_count = len(all_changes) - up_count - down_count

    # Value (Lowest PE > 0)
    value_stocks = sorted([s for s in stocks if s.get('市盈率') and s.get('市盈率') > 0], key=lambda x: x['市盈率'])[:5]
    
    # Momentum (Highest change)
    momentum_stocks = sorted([s for s in stocks if s.get('涨跌幅') is not None], key=lambda x: x['涨跌幅'], reverse=True)[:5]

    report = {
        "date": today_str,
        "indices": {
            "上证指数": {"price": 4078.64, "change": -0.19},
            "深证成指": {"price": 14830.46, "change": -1.10},
            "创业板指": {"price": 3596.71, "change": -1.43}
        },
        "stats": {
            "avg_change": round(avg_change, 2),
            "up": up_count,
            "down": down_count,
            "flat": flat_count
        },
        "watchlist": watchlist_data,
        "value": value_stocks,
        "momentum": momentum_stocks
    }
    
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    run()
