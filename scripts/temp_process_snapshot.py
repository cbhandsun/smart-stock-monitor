import json
import os
from datetime import datetime

# Paths
SNAPSHOT_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/cache/full_market_snapshot_2026-05-07.json"
WATCHLIST_PATH = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/data/watchlist.json"

def process():
    if not os.path.exists(SNAPSHOT_PATH):
        print(f"Error: Snapshot not found at {SNAPSHOT_PATH}")
        return

    with open(SNAPSHOT_PATH, 'r', encoding='utf-8') as f:
        stocks = json.load(f)

    with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
        watchlist_codes = json.load(f)

    # Market Overview
    all_changes = [s.get('涨跌幅') for s in stocks if s.get('涨跌幅') is not None]
    advances = [c for c in all_changes if c > 0]
    declines = [c for c in all_changes if c < 0]
    avg_change = sum(all_changes) / len(all_changes) if all_changes else 0

    # Watchlist Data
    watchlist_data = [s for s in stocks if s.get('代码') in watchlist_codes]

    # Sector-like logic (if possible) or just Top Gainer/Value
    # Top Gainers
    momentum = sorted([s for s in stocks if s.get('涨跌幅') is not None], key=lambda x: x['涨跌幅'], reverse=True)[:5]
    
    # Value (Low PB)
    value = sorted([s for s in stocks if s.get('市净率') is not None and s.get('市净率') > 0], key=lambda x: x['市净率'])[:5]

    print(json.dumps({
        "market": {
            "avg_change": avg_change,
            "advances": len(advances),
            "declines": len(declines),
            "total": len(stocks)
        },
        "watchlist": watchlist_data,
        "momentum": momentum,
        "value": value
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    process()
