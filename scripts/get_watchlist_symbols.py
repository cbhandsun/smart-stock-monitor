import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from modules.portfolio.watchlist_manager import WatchlistManager
    wm = WatchlistManager(user_id='default_user')
    portfolios = wm.list_portfolios()
    symbols = []
    for p in portfolios:
        for s in p.stocks:
            symbols.append(f"{s.symbol},{s.name}")
    print("\n".join(symbols))
except Exception as e:
    print(f"ERROR: {e}", file=sys.stderr)
