from celery import shared_task
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@shared_task
def generate_daily_report():
    """生成每日报告"""
    try:
        from main import get_market_overview, find_value_stocks, find_momentum_stocks
        from datetime import datetime
        import json
        
        # 收集数据
        market_overview = get_market_overview()
        value_stocks = find_value_stocks()
        momentum_stocks = find_momentum_stocks()
        
        report = {
            'date': datetime.now().isoformat(),
            'market_overview': market_overview.to_dict() if not market_overview.empty else {},
            'value_stocks': value_stocks.head(10).to_dict() if not value_stocks.empty else {},
            'momentum_stocks': momentum_stocks.head(10).to_dict() if not momentum_stocks.empty else {},
        }
        
        # 保存报告
        report_dir = './reports/daily'
        os.makedirs(report_dir, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%m-%d')
        report_path = f'{report_dir}/report_{date_str}.json'
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return f"Daily report saved to {report_path}"
        
    except Exception as e:
        return f"Error: {str(e)}"

@shared_task
def generate_weekly_report():
    """生成每周报告"""
    try:
        from datetime import datetime
        import json
        
        # TODO: 实现周报告生成逻辑
        
        report_dir = './reports/weekly'
        os.makedirs(report_dir, exist_ok=True)
        
        date_str = datetime.now().strftime('%Y-%W')
        report_path = f'{report_dir}/report_{date_str}.json'
        
        return f"Weekly report saved to {report_path}"
        
    except Exception as e:
        return f"Error: {str(e)}"

@shared_task
def generate_stock_report(symbol: str):
    """生成个股报告"""
    try:
        from main import generate_ai_report, get_stock_names_batch
        from modules.data_loader import fetch_research_reports, fetch_trading_signals
        from datetime import datetime
        import os
        
        name_map = get_stock_names_batch([symbol])
        stock_name = name_map.get(symbol, '')
        
        reports = fetch_research_reports(symbol)
        signals = fetch_trading_signals(symbol)
        
        ai_report = generate_ai_report(symbol, stock_name, reports, signals)
        
        # 保存报告
        report_dir = f"./reports/{datetime.now().strftime('%Y-%m-%d')}"
        os.makedirs(report_dir, exist_ok=True)
        
        report_path = f"{report_dir}/{symbol}.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(ai_report)
        
        return f"Stock report saved to {report_path}"
        
    except Exception as e:
        return f"Error: {str(e)}"
