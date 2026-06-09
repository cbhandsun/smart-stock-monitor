"""
页面模块包 - 共享上下文和工具函数
"""
import os
import json
import datetime
import logging

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHLIST_FILE = os.path.join(_BASE_DIR, "data", "watchlist.json")
REPORT_DIR = os.path.join(_BASE_DIR, "data", "reports")


def load_watchlist():
    """加载自选股列表 (PostgreSQL版)"""
    try:
        from database.models import get_db, UserPortfolio
        import streamlit as st
        
        user_id = 'default_user'
        if st.runtime.exists():
            user_id = st.session_state.get('user_id', 'default_user')
            
        db = get_db()
        session = db.get_session()
        
        # 查找名为 "默认自选" 的组合
        pf = session.query(UserPortfolio).filter_by(user_id=user_id, name="默认自选").first()
        if pf and pf.stocks:
            symbols = []
            for s in pf.stocks:
                if isinstance(s, dict):
                    symbols.append(s.get('symbol'))
                else:
                    symbols.append(s)
            session.close()
            # 过滤掉 None 或者空字符串
            return [sym for sym in symbols if sym]
            
        session.close()
    except Exception as e:
        logger.error(f"Failed to load watchlist from DB: {e}")
        
    # 如果数据库无数据，尝试读取文件做旧数据迁移，或者返回默认
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                symbols = json.load(f)
                # 顺便迁移到数据库
                save_watchlist(symbols)
                return symbols
        except Exception:
            pass
            
    return ["601318"]


def save_watchlist(stocks):
    """保存自选股列表 (PostgreSQL版)"""
    try:
        from database.models import get_db, UserPortfolio
        import streamlit as st
        
        user_id = 'default_user'
        if st.runtime.exists():
            user_id = st.session_state.get('user_id', 'default_user')
            
        db = get_db()
        session = db.get_session()
        
        # 转换格式为 [{"symbol": s} for s in stocks]
        stocks_data = [{
            "symbol": s, 
            "name": s, 
            "quantity": 0, 
            "avg_cost": 0.0, 
            "tags": [], 
            "notes": "", 
            "added_date": datetime.datetime.now().isoformat()
        } for s in stocks if s]
        
        pf = session.query(UserPortfolio).filter_by(user_id=user_id, name="默认自选").first()
        if pf:
            pf.stocks = stocks_data
            pf.updated_at = datetime.datetime.now()
        else:
            pf = UserPortfolio(
                id=f"watchlist_default_{user_id}",
                user_id=user_id,
                name="默认自选",
                description="系统默认自选股组合",
                stocks=stocks_data
            )
            session.add(pf)
            
        session.commit()
        session.close()
    except Exception as e:
        logger.error(f"Failed to save watchlist to DB: {e}")
        
    # 同时在本地写入一份做灾备兜底，防止数据库故障
    try:
        with open(WATCHLIST_FILE, "w") as f:
            json.dump(stocks, f)
    except Exception:
        pass


def load_cached_report(symbol: str):
    """加载缓存的AI报告 (PostgreSQL版)"""
    try:
        from database.models import get_db, ResearchReport
        
        db = get_db()
        session = db.get_session()
        today = datetime.datetime.now().date()
        
        # 查找今天最新的报告
        report = session.query(ResearchReport).filter(
            ResearchReport.symbol == symbol
        ).order_by(ResearchReport.report_date.desc()).first()
        
        if report and report.report_date and report.report_date.date() == today:
            content = report.content
            session.close()
            return content, True
            
        session.close()
    except Exception as e:
        logger.error(f"Failed to load cached report from DB for {symbol}: {e}")
        
    return None, False
