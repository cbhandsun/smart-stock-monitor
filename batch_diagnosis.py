import json
import os
import datetime
from modules.data_loader import fetch_trading_signals, fetch_research_reports
from modules.fundamentals import get_financial_health_score
from modules.quant import calculate_metrics
from ai_module import call_ai_for_stock_diagnosis # Need to ensure this is importable

WATCHLIST = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/watchlist.json"
REPORT_DIR = "/home/node/.openclaw/workspace-dev/smart-stock-monitor/reports"

def generate_and_save_reports():
    print("Starting batch diagnosis...")
    with open(WATCHLIST) as f:
        stocks = json.load(f)
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    save_path = f"{REPORT_DIR}/{date_str}"
    os.makedirs(save_path, exist_ok=True)
    
    for stock in stocks:
        print(f"Analyzing {stock}...")
        # Prepare Data
        formatted_symbol = "sh" + stock if stock.startswith('6') else "sz" + stock
        signals = fetch_trading_signals(formatted_symbol)
        reports = fetch_research_reports(stock)
        
        # Call AI
        # Mocking name for batch, or fetch it.
        # Simple fetch name:
        name = stock # Placeholder
        
        ai_text = call_ai_for_stock_diagnosis(stock, f"股票{stock}", reports, signals)
        
        # Save
        with open(f"{save_path}/{stock}.md", "w") as f:
            f.write(ai_text)
            
    print(f"Batch completed. Saved to {save_path}")

if __name__ == "__main__":
    generate_and_save_reports()
