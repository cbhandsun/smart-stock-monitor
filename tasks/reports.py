from celery import shared_task
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@shared_task
def generate_daily_report():
    """每日生成全量研报的调度器 (后台扫描所有用户持仓)"""
    try:
        from database.models import get_db, UserPortfolio, User
        from collections import Counter
        from datetime import datetime
        
        db = get_db()
        session = db.get_session()
        
        try:
            # 统计所有在持仓中的股票代码
            all_portfolios = session.query(UserPortfolio).all()
            symbol_counts = Counter()
            
            for pf in all_portfolios:
                if isinstance(pf.stocks, list):
                    for stock in pf.stocks:
                        if isinstance(stock, dict) and 'symbol' in stock:
                            symbol_counts[stock['symbol']] += 1
        finally:
            session.close()
                        
        if not symbol_counts:
            return "No stocks found in user portfolios."
            
        # 提取用户自选股中的所有唯一股票池，无数量上限
        target_symbols = list(symbol_counts.keys())
        
        print(f"[Daily Report Job] Target symbols: {target_symbols}")
        
        # 逐个压入单独任务，并使用 countdown 错峰，每隔 60 秒调度一个，防止 API 被限流
        for idx, symbol in enumerate(target_symbols):
            delay_seconds = idx * 60  # 每个间隔1分钟
            generate_stock_report.apply_async(args=[symbol], countdown=delay_seconds)
            
        return f"Dispatched {len(target_symbols)} stock report tasks with staggered delays."
        
    except Exception as e:
        import traceback
        return f"Error in daily report dispatcher: {str(e)}\n{traceback.format_exc()}"

@shared_task
def generate_weekly_report():
    """生成每周报告：汇总持仓表现 + 热点赛道 + 涨跌排行"""
    try:
        from datetime import datetime
        import json
        
        date_str = datetime.now().strftime('%Y-%W')
        report_dir = './reports/weekly'
        os.makedirs(report_dir, exist_ok=True)
        report_path = f'{report_dir}/report_{date_str}.json'
        
        # 1. 获取所有用户持仓股票池
        from database.models import get_db, UserPortfolio
        db = get_db()
        session = db.get_session()
        try:
            all_portfolios = session.query(UserPortfolio).all()
            all_symbols = set()
            for pf in all_portfolios:
                if isinstance(pf.stocks, list):
                    for stock in pf.stocks:
                        if isinstance(stock, dict) and 'symbol' in stock:
                            all_symbols.add(stock['symbol'])
        finally:
            session.close()
        
        # 2. 获取近一周行情数据 (Tushare 周线)
        from core.tushare_client import get_ts_client
        ts = get_ts_client()
        weekly_data = {}
        if ts.available and all_symbols:
            for symbol in list(all_symbols)[:30]:  # 限制前 30 只，防超时
                try:
                    kline = ts.get_weekly(symbol, limit=1)
                    if kline is not None and not kline.empty:
                        latest = kline.iloc[-1]
                        weekly_data[symbol] = {
                            'pct_chg': float(latest.get('涨跌幅', 0) or 0),
                            'close': float(latest.get('收盘', 0) or 0),
                        }
                except Exception:
                    pass
        
        # 3. 涨跌排行
        gainers = sorted(weekly_data.items(), key=lambda x: x[1]['pct_chg'], reverse=True)[:5]
        losers  = sorted(weekly_data.items(), key=lambda x: x[1]['pct_chg'])[:5]
        
        # 4. 写入报告 JSON
        report = {
            'week': date_str,
            'generated_at': datetime.now().isoformat(),
            'total_stocks': len(all_symbols),
            'top_gainers': gainers,
            'top_losers': losers,
            'summary': (
                f"本周持仓共 {len(all_symbols)} 只股票。"
                f"表现最佳: {', '.join(s for s, _ in gainers[:3])}；"
                f"回撤最大: {', '.join(s for s, _ in losers[:3])}。"
            )
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        return f"Weekly report saved to {report_path} ({len(all_symbols)} stocks tracked)"
        
    except Exception as e:
        import traceback
        return f"Error generating weekly report: {str(e)}\n{traceback.format_exc()}"

@shared_task
def generate_stock_report(symbol: str):
    """自动生成该股票的大模型研报，并入库到 Postgres"""
    try:
        from main import generate_ai_report, get_stock_names_batch
        from modules.data_loader import fetch_research_reports, fetch_trading_signals
        from database.models import get_db, ResearchReport
        from datetime import datetime
        
        # 抓取依赖
        name_map = get_stock_names_batch([symbol])
        stock_name = name_map.get(symbol, '')
        full_symbol = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
        
        # 同步生成 AI 报告内容（内部会消耗 Token，大约等待 10-20s）
        ai_report_content = generate_ai_report(symbol, stock_name, full_symbol)
        if "加载失败" in ai_report_content or len(ai_report_content) < 50:
            return f"Failed to generate meaningful report for {symbol}: {ai_report_content}"
            
        # 写入数据库 (ResearchReport表)
        db = get_db()
        session = db.get_session()
        
        try:
            # 删除今天已生成的重复报告
            today = datetime.now().date()
            existing = session.query(ResearchReport).filter(
                ResearchReport.symbol == symbol
            ).all()
            for r in existing:
                if r.report_date and r.report_date.date() == today:
                    session.delete(r)
            
            new_report = ResearchReport(
                symbol=symbol,
                title=f"AI Deep Diagnosis: {stock_name} ({symbol})",
                author="Quantum Pro AI",
                institution="Smart Stock Monitor",
                rating="Neutral",  # 大模型如果吐出固定格式提取更好，这里预留
                content=ai_report_content,
                report_date=datetime.now(),
                created_at=datetime.now()
            )
            
            session.add(new_report)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
        
        return f"Successfully saved DB report for {symbol}"
        
    except Exception as e:
        import traceback
        return f"Error generating stock {symbol} report: {str(e)}\n{traceback.format_exc()}"
