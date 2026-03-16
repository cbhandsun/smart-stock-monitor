import pickle
import json
import os
from typing import Optional, Any, Dict, List
from datetime import datetime, timedelta

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

class RedisCache:
    """Redis缓存层"""
    
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
            print(f"Redis连接失败: {e}")
            self.client = None
            self.enabled = False
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        if not self.enabled or not self.client:
            return None
        
        try:
            data = self.client.get(key)
            if data:
                return pickle.loads(data)
            return None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: int = 300):
        """设置缓存值"""
        if not self.enabled or not self.client:
            return False
        
        try:
            self.client.setex(key, expire, pickle.dumps(value))
            return True
        except Exception as e:
            print(f"Redis set error: {e}")
            return False
    
    def delete(self, key: str):
        """删除缓存"""
        if not self.enabled or not self.client:
            return False
        
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        """检查键是否存在"""
        if not self.enabled or not self.client:
            return False
        
        try:
            return self.client.exists(key) > 0
        except Exception as e:
            print(f"Redis exists error: {e}")
            return False
    
    def get_stock_data(self, symbol: str, data_type: str = "quote") -> Optional[Dict]:
        """获取股票数据缓存"""
        key = f"stock:{symbol}:{data_type}"
        return self.get(key)
    
    def set_stock_data(self, symbol: str, data: Any, data_type: str = "quote", expire: int = 60):
        """设置股票数据缓存"""
        key = f"stock:{symbol}:{data_type}"
        return self.set(key, data, expire)
    
    def get_kline_data(self, symbol: str, period: str = "daily") -> Optional[Any]:
        """获取K线数据缓存"""
        key = f"kline:{symbol}:{period}"
        return self.get(key)
    
    def set_kline_data(self, symbol: str, data: Any, period: str = "daily", expire: int = 300):
        """设置K线数据缓存"""
        key = f"kline:{symbol}:{period}"
        return self.set(key, data, expire)
    
    def get_market_overview(self) -> Optional[Any]:
        """获取市场概览缓存"""
        return self.get("market:overview")
    
    def set_market_overview(self, data: Any, expire: int = 60):
        """设置市场概览缓存"""
        return self.set("market:overview", data, expire)
    
    def get_fundamentals(self, symbol: str) -> Optional[Any]:
        """获取基本面数据缓存"""
        key = f"fundamentals:{symbol}"
        return self.get(key)
    
    def set_fundamentals(self, symbol: str, data: Any, expire: int = 3600):
        """设置基本面数据缓存"""
        key = f"fundamentals:{symbol}"
        return self.set(key, data, expire)
    
    def get_user_session(self, user_id: str) -> Optional[Any]:
        """获取用户会话缓存"""
        key = f"session:{user_id}"
        return self.get(key)
    
    def set_user_session(self, user_id: str, data: Any, expire: int = 3600):
        """设置用户会话缓存"""
        key = f"session:{user_id}"
        return self.set(key, data, expire)
    
    def delete_user_session(self, user_id: str):
        """删除用户会话缓存"""
        key = f"session:{user_id}"
        return self.delete(key)
    
    def get_ai_response_cache(self, prompt_hash: str) -> Optional[str]:
        """获取AI响应缓存"""
        key = f"ai:response:{prompt_hash}"
        return self.get(key)
    
    def set_ai_response_cache(self, prompt_hash: str, response: str, expire: int = 3600):
        """设置AI响应缓存"""
        key = f"ai:response:{prompt_hash}"
        return self.set(key, response, expire)
    
    def increment_counter(self, key: str, amount: int = 1) -> int:
        """增加计数器"""
        if not self.enabled or not self.client:
            return 0
        
        try:
            return self.client.incr(key, amount)
        except Exception as e:
            print(f"Redis increment error: {e}")
            return 0
    
    def get_counter(self, key: str) -> int:
        """获取计数器值"""
        if not self.enabled or not self.client:
            return 0
        
        try:
            value = self.client.get(key)
            return int(value) if value else 0
        except Exception as e:
            print(f"Redis get counter error: {e}")
            return 0
    
    def set_counter(self, key: str, value: int, expire: int = None):
        """设置计数器值"""
        if not self.enabled or not self.client:
            return False
        
        try:
            self.client.set(key, value, ex=expire)
            return True
        except Exception as e:
            print(f"Redis set counter error: {e}")
            return False
    
    def add_to_set(self, key: str, *members):
        """添加到集合"""
        if not self.enabled or not self.client:
            return False
        
        try:
            self.client.sadd(key, *members)
            return True
        except Exception as e:
            print(f"Redis sadd error: {e}")
            return False
    
    def get_set_members(self, key: str) -> set:
        """获取集合成员"""
        if not self.enabled or not self.client:
            return set()
        
        try:
            return self.client.smembers(key)
        except Exception as e:
            print(f"Redis smembers error: {e}")
            return set()
    
    def clear_pattern(self, pattern: str):
        """清除匹配模式的所有键"""
        if not self.enabled or not self.client:
            return 0
        
        try:
            keys = self.client.keys(pattern)
            if keys:
                return self.client.delete(*keys)
            return 0
        except Exception as e:
            print(f"Redis clear pattern error: {e}")
            return 0
    
    def ping(self) -> bool:
        """检查Redis连接"""
        if not self.enabled or not self.client:
            return False
        
        try:
            return self.client.ping()
        except:
            return False
