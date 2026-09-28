"""统一的磁盘缓存层 (按日期 key 存取 DataFrame)"""

import os
import json
import datetime
import logging
import pandas as pd

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(CACHE_DIR, exist_ok=True)


def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def get_cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}_{_today()}.json")


def load_df(key: str) -> pd.DataFrame | None:
    """从磁盘加载当日缓存的 DataFrame，不存在返回 None。"""
    path = get_cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return pd.DataFrame(data)
    except Exception as e:
        logger.warning(f"Cache load failed for '{key}': {e}")
        return None


def save_df(key: str, df: pd.DataFrame) -> None:
    """将 DataFrame 保存到当日缓存。"""
    if df is None or df.empty:
        return
    path = get_cache_path(key)
    try:
        df.to_json(path, orient="records", force_ascii=False)
    except Exception as e:
        logger.error(f"Cache save failed for '{key}': {e}")


def load_report(symbol: str) -> tuple[str | None, bool]:
    """读取当日 AI 报告缓存。返回 (内容, 是否有缓存)。"""
    path = os.path.join(REPORT_DIR, _today(), f"{symbol}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), True
    return None, False


def save_report(symbol: str, content: str) -> None:
    """保存 AI 报告到当日缓存。"""
    dir_path = os.path.join(REPORT_DIR, _today())
    os.makedirs(dir_path, exist_ok=True)
    path = os.path.join(dir_path, f"{symbol}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
