
import os
import sys
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append('/home/juhongtao/openclaw/config/workspace-dev/smart-stock-monitor')

from core.tushare_client import get_ts_client

def check_stock_pe(code):
    full = ("sh" if code.startswith('6') else "sz") + code
    print(f"Checking {full}...")
    
    # 1. Check daily basic
    basic = get_ts_client().get_daily_basic(full, limit=5)
    if basic is not None and not basic.empty:
        print("Daily Basic Data Found:")
        print(basic[['trade_date', 'pe', 'pe_ttm', 'pb']].head())
    else:
        print("No Daily Basic data found in Tushare/PG.")

if __name__ == "__main__":
    # Test with some random stocks
    stocks = ['600036', '000001', '300750', '601318']
    for s in stocks:
        check_stock_pe(s)
        print("-" * 30)
