"""
文件缓存工具 — 当日 JSON 持久化层 (L2 缓存)
从 main.py 剥离，作为独立的缓存工具模块复用。
"""
import os
import glob
import time
import logging
import datetime
import json
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(key: str, date_str: str = None) -> str:
    """生成缓存文件路径"""
    if date_str is None:
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    return os.path.join(CACHE_DIR, f"{key}_{date_str}.json")


def load_from_cache(key: str) -> Optional[pd.DataFrame]:
    """
    从当日文件缓存读取 DataFrame。
    交易时段内：缓存有效期 5 分钟（防止 09:30 前空数据霸屏全天）
    非交易时段：使用当日文件（日内不变）
    """
    path = get_cache_path(key)
    if not os.path.exists(path):
        return None

    # 交易时段内加 5 分钟 TTL 检查，避免早盘前的空数据缓存霸屏全天
    now = datetime.datetime.now()
    is_trading = (
        now.weekday() < 5
        and datetime.time(9, 25) <= now.time() <= datetime.time(15, 5)
    )
    if is_trading:
        file_age = time.time() - os.path.getmtime(path)
        if file_age > 300:  # 5 分钟
            logger.debug(f"文件缓存已过期 (交易时段 5min TTL): {key}")
            return None

    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return pd.DataFrame(data)
    except (json.JSONDecodeError, ValueError, KeyError) as e:
        logger.warning(f"缓存读取失败 {path}: {e}")
        return None


def save_to_cache(key: str, df: pd.DataFrame):
    """将 DataFrame 写入当日文件缓存"""
    if df is None or df.empty:
        return
    path = get_cache_path(key)
    try:
        df.to_json(path, orient='records', force_ascii=False)
    except Exception as e:
        logger.warning(f"缓存写入失败 {path}: {e}")


def cleanup_old_cache(max_age_days: int = 7):
    """清理超过 N 天的缓存文件"""
    now = time.time()
    removed = 0
    for f in glob.glob(os.path.join(CACHE_DIR, "*.json")):
        if now - os.path.getmtime(f) > max_age_days * 86400:
            try:
                os.remove(f)
                removed += 1
            except OSError as e:
                logger.warning(f"清理缓存文件失败 {f}: {e}")
    if removed:
        logger.info(f"已清理 {removed} 个过期缓存文件")
    return removed
