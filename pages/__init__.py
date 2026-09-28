"""
页面模块包 - 共享上下文和工具函数
"""

import os
import datetime
import logging
from uuid import uuid4

from core.user_context import require_user_id

logger = logging.getLogger(__name__)

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_DIR = os.path.join(_BASE_DIR, "data", "reports")


def load_watchlist():
    """加载自选股列表 (PostgreSQL版)"""
    from database.models import UserPortfolio, get_db

    user_id = require_user_id()
    session = get_db().get_session()
    try:
        pf = (
            session.query(UserPortfolio)
            .filter_by(user_id=user_id, name="默认自选")
            .first()
        )
        if pf and pf.stocks:
            symbols: list[str] = []
            for s in pf.stocks:
                value = s.get("symbol") if isinstance(s, dict) else s
                if isinstance(value, str) and value.isdigit() and len(value) == 6:
                    symbols.append(value)
            return list(dict.fromkeys(symbols))
        return []
    except Exception:
        logger.error("Failed to load the authenticated user's watchlist")
        raise
    finally:
        session.close()


def save_watchlist(stocks):
    """保存自选股列表 (PostgreSQL版)"""
    from database.models import UserPortfolio, get_db

    if not isinstance(stocks, (list, tuple, set)) or len(stocks) > 500:
        raise ValueError("自选股列表格式不正确或超过500只上限")
    symbols: list[str] = []
    for stock in stocks:
        if not isinstance(stock, str) or not stock.isdigit() or len(stock) != 6:
            raise ValueError("自选股代码必须是6位数字")
        if stock not in symbols:
            symbols.append(stock)

    user_id = require_user_id()
    session = get_db().get_session()
    try:
        stocks_data = [
            {
                "symbol": s,
                "name": s,
                "quantity": 0,
                "avg_cost": 0.0,
                "tags": [],
                "notes": "",
                "added_date": datetime.datetime.now().isoformat(),
            }
            for s in symbols
        ]

        pf = (
            session.query(UserPortfolio)
            .filter_by(user_id=user_id, name="默认自选")
            .first()
        )
        if pf:
            pf.stocks = stocks_data
            pf.updated_at = datetime.datetime.now()
        else:
            pf = UserPortfolio(
                id=f"portfolio_{uuid4().hex}",
                user_id=user_id,
                name="默认自选",
                description="系统默认自选股组合",
                stocks=stocks_data,
            )
            session.add(pf)

        session.commit()
    except Exception:
        session.rollback()
        logger.error("Failed to save the authenticated user's watchlist")
        raise
    finally:
        session.close()


def load_cached_report(symbol: str):
    """加载缓存的AI报告 (PostgreSQL版)"""
    try:
        from database.models import get_db, ResearchReport

        db = get_db()
        session = db.get_session()
        today = datetime.datetime.now().date()

        # 查找今天最新的报告
        report = (
            session.query(ResearchReport)
            .filter(ResearchReport.symbol == symbol)
            .order_by(ResearchReport.report_date.desc())
            .first()
        )

        if report and report.report_date and report.report_date.date() == today:
            content = report.content
            session.close()
            return content, True

        session.close()
    except Exception:
        logger.error("Cached report read failed")

    return None, False
