"""
Redis 缓存层 — 安全 JSON 序列化版本
使用 JSON + 自定义 DataFrame 编解码替代 pickle，消除反序列化 RCE 风险。
"""
import json
import os
import logging
from typing import Optional, Any, Dict
from datetime import datetime

import pandas as pd

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)


# ============================================================
#  JSON 安全编解码 (DataFrame / dict / list / scalar 全覆盖)
# ============================================================

def _encode(value: Any) -> bytes:
    """将 Python 对象编码为 JSON bytes，支持 DataFrame。"""
    if isinstance(value, pd.DataFrame):
        payload = {
            "__type__": "dataframe",
            "data": value.to_dict(orient="records"),
            "columns": list(value.columns),
        }
    elif isinstance(value, pd.Series):
        payload = {
            "__type__": "series",
            "data": value.to_dict(),
            "name": value.name,
        }
    else:
        payload = {"__type__": "raw", "data": value}

    return json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")


def _decode(raw: bytes) -> Any:
    """将 JSON bytes 解码回 Python 对象。"""
    payload = json.loads(raw.decode("utf-8"))
    t = payload.get("__type__", "raw")
    if t == "dataframe":
        return pd.DataFrame(payload["data"], columns=payload["columns"])
    elif t == "series":
        return pd.Series(payload["data"], name=payload["name"])
    else:
        return payload["data"]


# ============================================================
#  RedisCache
# ============================================================

class RedisCache:
    """Redis 缓存层 (JSON 安全序列化)"""

    def __init__(self, host=None, port=None, db=0, password=None):
        host = host or os.getenv('REDIS_HOST', 'localhost')
        port = port or int(os.getenv('REDIS_PORT', '6379'))
        password = password or os.getenv('REDIS_PASSWORD', None)
        if not REDIS_AVAILABLE:
            self.enabled = False
            self.client = None
            return
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=False,
                socket_connect_timeout=5
            )
            self.enabled = True
        except Exception as e:
            logger.warning(f"Redis 连接失败: {e}")
            self.client = None
            self.enabled = False

    # ---- 基础读写 ----

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self.enabled or not self.client:
            return None
        try:
            data = self.client.get(key)
            if data:
                return _decode(data)
            return None
        except Exception as e:
            logger.debug(f"Redis get error [{key}]: {e}")
            return None

    def set(self, key: str, value: Any, expire: int = 300) -> bool:
        """设置缓存值"""
        if not self.enabled or not self.client:
            return False
        try:
            self.client.setex(key, expire, _encode(value))
            return True
        except Exception as e:
            logger.debug(f"Redis set error [{key}]: {e}")
            return False

    def delete(self, key: str) -> bool:
        """删除缓存"""
        if not self.enabled or not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.debug(f"Redis delete error [{key}]: {e}")
            return False

    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self.enabled or not self.client:
            return False
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.debug(f"Redis exists error [{key}]: {e}")
            return False

    # ---- 股票数据专用 ----

    def get_stock_data(self, symbol: str, data_type: str = "quote") -> Optional[Dict]:
        return self.get(f"stock:{symbol}:{data_type}")

    def set_stock_data(self, symbol: str, data: Any, data_type: str = "quote", expire: int = 60):
        return self.set(f"stock:{symbol}:{data_type}", data, expire)

    def get_kline_data(self, symbol: str, period: str = "daily") -> Optional[Any]:
        return self.get(f"kline:{symbol}:{period}")

    def set_kline_data(self, symbol: str, data: Any, period: str = "daily", expire: int = 300):
        return self.set(f"kline:{symbol}:{period}", data, expire)

    def get_market_overview(self) -> Optional[Any]:
        return self.get("market:overview")

    def set_market_overview(self, data: Any, expire: int = 60):
        return self.set("market:overview", data, expire)

    def get_fundamentals(self, symbol: str) -> Optional[Any]:
        return self.get(f"fundamentals:{symbol}")

    def set_fundamentals(self, symbol: str, data: Any, expire: int = 3600):
        return self.set(f"fundamentals:{symbol}", data, expire)

    # ---- 用户会话 ----

    def get_user_session(self, user_id: str) -> Optional[Any]:
        return self.get(f"session:{user_id}")

    def set_user_session(self, user_id: str, data: Any, expire: int = 3600):
        return self.set(f"session:{user_id}", data, expire)

    def delete_user_session(self, user_id: str):
        return self.delete(f"session:{user_id}")

    # ---- AI 响应缓存 ----

    def get_ai_response_cache(self, prompt_hash: str) -> Optional[str]:
        return self.get(f"ai:response:{prompt_hash}")

    def set_ai_response_cache(self, prompt_hash: str, response: str, expire: int = 3600):
        return self.set(f"ai:response:{prompt_hash}", response, expire)

    # ---- 计数器 ----

    def increment_counter(self, key: str, amount: int = 1) -> int:
        if not self.enabled or not self.client:
            return 0
        try:
            return self.client.incr(key, amount)
        except Exception as e:
            logger.debug(f"Redis increment error [{key}]: {e}")
            return 0

    def get_counter(self, key: str) -> int:
        if not self.enabled or not self.client:
            return 0
        try:
            value = self.client.get(key)
            return int(value) if value else 0
        except Exception as e:
            logger.debug(f"Redis get counter error [{key}]: {e}")
            return 0

    def set_counter(self, key: str, value: int, expire: int = None) -> bool:
        if not self.enabled or not self.client:
            return False
        try:
            self.client.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.debug(f"Redis set counter error [{key}]: {e}")
            return False

    # ---- 集合操作 ----

    def add_to_set(self, key: str, *members) -> bool:
        if not self.enabled or not self.client:
            return False
        try:
            self.client.sadd(key, *members)
            return True
        except Exception as e:
            logger.debug(f"Redis sadd error [{key}]: {e}")
            return False

    def get_set_members(self, key: str) -> set:
        if not self.enabled or not self.client:
            return set()
        try:
            return self.client.smembers(key)
        except Exception as e:
            logger.debug(f"Redis smembers error [{key}]: {e}")
            return set()

    def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的所有键"""
        if not self.enabled or not self.client:
            return 0
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            logger.debug(f"Redis clear pattern error [{pattern}]: {e}")
            return 0

    def ping(self) -> bool:
        """检查 Redis 连接"""
        if not self.enabled or not self.client:
            return False
        try:
            return self.client.ping()
        except Exception:
            return False
