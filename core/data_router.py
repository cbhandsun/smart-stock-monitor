"""
多数据源路由系统
解决单点故障问题，支持 AkShare、Tushare、Baostock 等多个数据源自动切换
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

try:
    from core.cache import RedisCache
    _redis_cache = RedisCache()
    if not _redis_cache.ping():
        _redis_cache = None
except Exception:
    _redis_cache = None

logger = logging.getLogger(__name__)


@dataclass
class DataSourceStatus:
    """数据源状态"""
    name: str
    is_available: bool
    last_check: datetime
    response_time_ms: float
    error_count: int = 0


class DataSource(ABC):
    """数据源抽象基类"""
    
    def __init__(self, name: str, priority: int = 1):
        self.name = name
        self.priority = priority
        self.status = DataSourceStatus(
            name=name,
            is_available=True,
            last_check=datetime.now(),
            response_time_ms=0
        )
    
    @abstractmethod
    def get_daily(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取日线数据"""
        pass
    
    @abstractmethod
    def get_realtime(self, symbol: str) -> Optional[Dict]:
        """获取实时行情"""
        pass
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            start = time.time()
            # 使用上证指数做健康检查
            result = self.get_realtime("sh000001")
            self.status.response_time_ms = (time.time() - start) * 1000
            self.status.is_available = result is not None
            self.status.last_check = datetime.now()
            if result:
                self.status.error_count = 0
            return self.status.is_available
        except Exception as e:
            self.status.is_available = False
            self.status.error_count += 1
            logger.warning(f"{self.name} 健康检查失败: {e}")
            return False


class AkshareSource(DataSource):
    """AkShare 数据源"""
    
    def __init__(self):
        super().__init__("AkShare", priority=3)
        self._ak = None
    
    def _get_ak(self):
        """懒加载 akshare"""
        if self._ak is None:
            import akshare as ak
            self._ak = ak
        return self._ak
    
    def get_daily(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取日线数据"""
        try:
            ak = self._get_ak()
            # 处理代码格式
            if symbol.startswith(('sh', 'sz')):
                code = symbol[2:]
            else:
                code = symbol
            
            df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                   start_date="20230101", adjust="qfq")
            if df is not None and not df.empty:
                return df
            return None
        except Exception as e:
            logger.error(f"AkShare 获取日线失败 {symbol}: {e}")
            return None
    
    def get_realtime(self, symbol: str) -> Optional[Dict]:
        """获取实时行情"""
        try:
            ak = self._get_ak()
            df = ak.stock_zh_a_spot_em()
            
            # 匹配股票代码
            if symbol.startswith(('sh', 'sz')):
                code = symbol[2:]
            else:
                code = symbol
            
            row = df[df['代码'] == code]
            if not row.empty:
                return {
                    'symbol': symbol,
                    'name': row.iloc[0]['名称'],
                    'price': float(row.iloc[0]['最新价']),
                    'change_pct': float(row.iloc[0]['涨跌幅']),
                    'volume': int(row.iloc[0]['成交量']),
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"AkShare 获取实时行情失败 {symbol}: {e}")
            return None


class TushareSource(DataSource):
    """Tushare 数据源（需要 API Key）"""
    
    def __init__(self, token: Optional[str] = None):
        super().__init__("Tushare", priority=1)
        self.token = token or os.getenv("TUSHARE_TOKEN")
        self._pro = None
    
    def _get_pro(self):
        """懒加载 tushare"""
        if self._pro is None and self.token:
            import tushare as ts
            self._pro = ts.pro_api(self.token)
        return self._pro
    
    def get_daily(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取日线数据"""
        if not self.token:
            return None
        
        try:
            pro = self._get_pro()
            if not pro:
                return None
            
            # 转换代码格式
            if symbol.startswith('sh'):
                ts_code = symbol[2:] + '.SH'
            elif symbol.startswith('sz'):
                ts_code = symbol[2:] + '.SZ'
            else:
                ts_code = symbol
            
            df = pro.daily(ts_code=ts_code)
            return df if not df.empty else None
        except Exception as e:
            logger.error(f"Tushare 获取日线失败 {symbol}: {e}")
            return None
    
    def get_realtime(self, symbol: str) -> Optional[Dict]:
        """获取实时行情（Tushare 实时数据需要订阅）"""
        # Tushare 免费版不提供实时数据，返回 None
        return None


class BaostockSource(DataSource):
    """Baostock 数据源"""
    
    def __init__(self):
        super().__init__("Baostock", priority=3)
        self._bs = None
        self._logged_in = False
    
    def _login(self):
        """登录 Baostock"""
        if not self._logged_in:
            try:
                import baostock as bs
                self._bs = bs
                result = bs.login()
                if result.error_code == '0':
                    self._logged_in = True
                    return True
            except Exception as e:
                logger.error(f"Baostock 登录失败: {e}")
        return self._logged_in
    
    def get_daily(self, symbol: str) -> Optional[pd.DataFrame]:
        """获取日线数据"""
        if not self._login():
            return None
        
        try:
            # 转换代码格式
            if symbol.startswith('sh'):
                code = f"sh.{symbol[2:]}"
            elif symbol.startswith('sz'):
                code = f"sz.{symbol[2:]}"
            else:
                code = symbol
            
            rs = self._bs.query_history_k_data_plus(
                code,
                "date,code,open,high,low,close,volume,amount",
                start_date='2023-01-01',
                frequency='d'
            )
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            if data_list:
                df = pd.DataFrame(data_list, columns=rs.fields)
                return df
            return None
        except Exception as e:
            logger.error(f"Baostock 获取日线失败 {symbol}: {e}")
            return None
    
    def get_realtime(self, symbol: str) -> Optional[Dict]:
        """Baostock 不提供实时数据"""
        return None


class DataRouter:
    """
    数据路由器 - 自动选择和切换数据源
    """
    
    def __init__(self):
        self.sources: List[DataSource] = []
        self._init_sources()
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 60  # 缓存60秒
    
    def _init_sources(self):
        """初始化所有数据源"""
        tushare_token = os.getenv("TUSHARE_TOKEN")
        if tushare_token:
            self.sources.append(TushareSource(tushare_token))

        # AkShare 降为备选
        self.sources.append(AkshareSource())

        self.sources.append(BaostockSource())

        # 按优先级排序
        self.sources.sort(key=lambda x: x.priority)
    
    def health_check_all(self) -> Dict[str, bool]:
        """检查所有数据源健康状态"""
        results = {}
        for source in self.sources:
            results[source.name] = source.health_check()
        return results
    
    def get_daily(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        获取日线数据 - Redis L1 + 内存 L2 + 自动切换数据源
        """
        cache_key = f"router:daily:{symbol}"
        
        # L1: Redis
        if _redis_cache:
            cached = _redis_cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Redis 缓存命中: {symbol}")
                return cached
        
        # L2: 内存缓存
        mem_key = f"daily_{symbol}"
        if mem_key in self.cache:
            cached_time, data = self.cache[mem_key]
            if (datetime.now() - cached_time).seconds < self.cache_ttl:
                logger.debug(f"内存缓存命中: {symbol}")
                return data
        
        # 按优先级尝试各个数据源
        for source in self.sources:
            try:
                logger.info(f"尝试从 {source.name} 获取 {symbol}")
                df = source.get_daily(symbol)
                if df is not None and not df.empty:
                    # 写入双层缓存
                    self.cache[mem_key] = (datetime.now(), df)
                    if _redis_cache:
                        _redis_cache.set(cache_key, df, expire=300)
                    logger.info(f"✅ {source.name} 成功获取 {symbol}")
                    return df
            except Exception as e:
                logger.warning(f"❌ {source.name} 获取失败: {e}")
                continue
        
        logger.error(f"所有数据源都无法获取 {symbol}")
        return None
    
    def get_realtime(self, symbol: str) -> Optional[Dict]:
        """
        获取实时行情 - Redis L1 + 内存 L2 + 自动切换数据源
        """
        cache_key = f"router:realtime:{symbol}"
        
        # L1: Redis (实时数据 10s)
        if _redis_cache:
            cached = _redis_cache.get(cache_key)
            if cached is not None:
                return cached
        
        # L2: 内存缓存 5s
        mem_key = f"realtime_{symbol}"
        if mem_key in self.cache:
            cached_time, data = self.cache[mem_key]
            if (datetime.now() - cached_time).seconds < 5:
                return data
        
        for source in self.sources:
            try:
                data = source.get_realtime(symbol)
                if data:
                    self.cache[mem_key] = (datetime.now(), data)
                    if _redis_cache:
                        _redis_cache.set(cache_key, data, expire=10)
                    return data
            except Exception as e:
                logger.warning(f"{source.name} 获取实时数据失败: {e}")
                continue
        
        return None
    
    def get_status_report(self) -> str:
        """获取数据源状态报告"""
        lines = ["📊 数据源状态报告", "=" * 40]
        
        for source in self.sources:
            status = "🟢 正常" if source.status.is_available else "🔴 异常"
            lines.append(f"{status} {source.name}")
            lines.append(f"   响应时间: {source.status.response_time_ms:.1f}ms")
            lines.append(f"   错误次数: {source.status.error_count}")
            lines.append(f"   最后检查: {source.status.last_check.strftime('%H:%M:%S')}")
        
        return "\n".join(lines)


# 全局数据路由器实例
_router = None

def get_router() -> DataRouter:
    """获取全局数据路由器（单例）"""
    global _router
    if _router is None:
        _router = DataRouter()
    return _router


# 便捷函数
def fetch_daily(symbol: str) -> Optional[pd.DataFrame]:
    """获取日线数据"""
    return get_router().get_daily(symbol)

def fetch_realtime(symbol: str) -> Optional[Dict]:
    """获取实时行情"""
    return get_router().get_realtime(symbol)

def check_data_sources() -> str:
    """检查数据源状态"""
    router = get_router()
    router.health_check_all()
    return router.get_status_report()


if __name__ == "__main__":
    # 测试数据路由器
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("数据路由器测试")
    print("=" * 60)
    
    # 检查数据源状态
    print("\n1. 数据源健康检查")
    print(check_data_sources())
    
    # 测试获取数据
    print("\n2. 测试获取上证指数日线")
    df = fetch_daily("sh000001")
    if df is not None:
        print(f"✅ 成功获取 {len(df)} 条数据")
        print(df.tail())
    else:
        print("❌ 获取失败")
    
    print("\n3. 测试获取实时行情")
    rt = fetch_realtime("sh000001")
    if rt:
        print(f"✅ 实时行情: {rt}")
    else:
        print("❌ 获取失败")
