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
    """加载自选股列表"""
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Watchlist 读取失败: {e}")
    return ["601318"]


def save_watchlist(stocks):
    """保存自选股列表"""
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(stocks, f)


def load_cached_report(symbol):
    """加载缓存的AI报告"""
    path = f"{REPORT_DIR}/{datetime.datetime.now().strftime('%Y-%m-%d')}/{symbol}.md"
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read(), True
    return None, False
