"""
tests/test_data_router.py — 数据路由器测试
"""
import pytest
import pandas as pd
from datetime import datetime

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.data_router import DataSource, DataSourceStatus, DataRouter


class MockSource(DataSource):
    """用于测试的模拟数据源"""

    def __init__(self, name="MockSource", priority=1, data=None, fail=False):
        super().__init__(name, priority)
        self._data = data
        self._fail = fail

    def get_daily(self, symbol):
        if self._fail:
            raise ConnectionError("Mock failure")
        return self._data

    def get_realtime(self, symbol):
        if self._fail:
            raise ConnectionError("Mock failure")
        return {"price": 100.0, "symbol": symbol} if self._data is not None else None


class TestDataSourceStatus:
    def test_default_values(self):
        status = DataSourceStatus(name="test", is_available=True,
                                  last_check=datetime.now(), response_time_ms=0)
        assert status.error_count == 0
        assert status.is_available is True


class TestDataSource:
    def test_health_check_success(self):
        source = MockSource(data=pd.DataFrame({"a": [1]}))
        assert source.health_check() is True
        assert source.status.is_available is True

    def test_health_check_failure(self):
        source = MockSource(fail=True)
        result = source.health_check()
        assert result is False
        assert source.status.is_available is False
        assert source.status.error_count == 1


class TestDataRouter:
    def test_add_source(self):
        router = DataRouter()
        source = MockSource(name="S1")
        router.add_source(source)
        assert len(router.sources) == 1

    def test_get_daily_returns_data(self):
        mock_df = pd.DataFrame({"收盘": [100, 101]})
        router = DataRouter()
        router.add_source(MockSource(data=mock_df))
        result = router.get_daily("sh601318")
        assert result is not None
        assert not result.empty

    def test_failover_to_next_source(self):
        mock_df = pd.DataFrame({"收盘": [100, 101]})
        router = DataRouter()
        router.add_source(MockSource(name="Broken", fail=True, priority=1))
        router.add_source(MockSource(name="Working", data=mock_df, priority=2))
        result = router.get_daily("sh601318")
        assert result is not None

    def test_all_sources_fail(self):
        router = DataRouter()
        router.add_source(MockSource(name="Broken1", fail=True))
        router.add_source(MockSource(name="Broken2", fail=True))
        result = router.get_daily("sh601318")
        assert result is None

    def test_get_status(self):
        router = DataRouter()
        router.add_source(MockSource(name="S1"))
        status = router.get_status()
        assert len(status) == 1
        assert status[0].name == "S1"
