"""
tests/test_data_router.py — 数据路由器测试
"""

import pytest
import pandas as pd
from datetime import datetime

import sys
import os

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
        status = DataSourceStatus(
            name="test",
            is_available=True,
            last_check=datetime.now(),
            response_time_ms=0,
        )
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
    @pytest.fixture(autouse=True)
    def setup_mocks(self):
        from unittest.mock import patch

        with patch("core.data_router._redis_cache", None):
            yield

    def test_add_source(self):
        router = DataRouter()
        router.sources = []
        source = MockSource(name="S1")
        router.add_source(source)
        assert len(router.sources) == 1

    def test_get_daily_returns_data(self):
        mock_df = pd.DataFrame({"收盘": [100, 101]})
        router = DataRouter()
        router.sources = []
        router.add_source(MockSource(data=mock_df))
        result = router.get_daily("sh601318")
        assert result is not None
        assert not result.empty

    def test_failover_to_next_source(self):
        mock_df = pd.DataFrame({"收盘": [100, 101]})
        router = DataRouter()
        router.sources = []
        router.add_source(MockSource(name="Broken", fail=True, priority=1))
        router.add_source(MockSource(name="Working", data=mock_df, priority=2))
        result = router.get_daily("sh601318")
        assert result is not None

    def test_all_sources_fail(self):
        router = DataRouter()
        router.sources = []
        router.add_source(MockSource(name="Broken1", fail=True))
        router.add_source(MockSource(name="Broken2", fail=True))
        result = router.get_daily("sh601318")
        assert result is None

    def test_get_status(self):
        router = DataRouter()
        router.sources = []
        router.add_source(MockSource(name="S1"))
        status = router.get_status()
        assert len(status) == 1
        assert status[0].name == "S1"

class TestAkshareCircuitBreakerIntegration:
    @pytest.fixture(autouse=True)
    def reset_cb(self):
        from core.circuit_breaker import akshare_circuit_breaker
        akshare_circuit_breaker.reset()
        yield
        akshare_circuit_breaker.reset()

    def test_akshare_source_circuit_breaker_open_skips_call(self):
        from unittest.mock import MagicMock
        from core.circuit_breaker import akshare_circuit_breaker
        from core.data_router import AkshareSource

        source = AkshareSource()
        mock_ak = MagicMock()
        source._ak = mock_ak

        # Trip the circuit breaker
        for _ in range(3):
            akshare_circuit_breaker.record_failure()
        assert akshare_circuit_breaker.is_open

        # Calls should return None immediately without touching mock_ak
        assert source.get_daily("sh600000") is None
        assert source.get_realtime("sh600000") is None
        assert mock_ak.stock_zh_a_hist.call_count == 0
        assert mock_ak.stock_zh_a_spot_em.call_count == 0

    def test_akshare_source_records_success_and_failure(self):
        from unittest.mock import MagicMock
        from core.circuit_breaker import akshare_circuit_breaker
        from core.data_router import AkshareSource

        source = AkshareSource()
        mock_ak = MagicMock()
        source._ak = mock_ak

        # Simulated exception records failure
        mock_ak.stock_zh_a_hist.side_effect = ConnectionError("Remote down")
        assert source.get_daily("sh600000") is None
        assert akshare_circuit_breaker._consecutive_failures == 1

        # Simulated success records success and resets failure counter
        mock_ak.stock_zh_a_hist.side_effect = None
        mock_ak.stock_zh_a_hist.return_value = pd.DataFrame({"收盘": [10.5]})
        res = source.get_daily("sh600000")
        assert res is not None
        assert akshare_circuit_breaker._consecutive_failures == 0

