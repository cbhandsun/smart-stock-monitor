import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from database.models import get_db
    db = get_db()
    portfolios = db.get_user_portfolios('default_user')
    for p in portfolios:
        print(f"Portfolio: {p.name}")
        for s in (p.stocks or []):
            print(f" - {s.get('symbol')}, {s.get('name')}")
except Exception as e:
    print(f"ERROR: {e}")
