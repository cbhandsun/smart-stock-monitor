"""
tests/test_cache.py — Redis 缓存 JSON 编解码测试
不依赖真实 Redis 连接，只测试 _encode/_decode 编解码轮转
"""
import sys
import os
import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.cache import _encode, _decode


class TestJsonCodec:
    """测试 _encode / _decode 往返正确性"""

    def test_dict_roundtrip(self):
        data = {"a": 1, "b": "hello", "c": 3.14}
        assert _decode(_encode(data)) == data

    def test_list_roundtrip(self):
        data = [1, 2, 3, "x"]
        assert _decode(_encode(data)) == data

    def test_scalar_roundtrip(self):
        assert _decode(_encode(42)) == 42
        assert _decode(_encode("string")) == "string"
        assert _decode(_encode(None)) is None

    def test_dataframe_roundtrip(self):
        df = pd.DataFrame({
            "a": [1, 2, 3],
            "b": [1.1, 2.2, 3.3],
            "c": ["x", "y", "z"],
        })
        decoded = _decode(_encode(df))
        assert isinstance(decoded, pd.DataFrame)
        pd.testing.assert_frame_equal(decoded.reset_index(drop=True),
                                      df.reset_index(drop=True))

    def test_empty_dataframe_roundtrip(self):
        df = pd.DataFrame()
        decoded = _decode(_encode(df))
        assert isinstance(decoded, pd.DataFrame)
        assert decoded.empty

    def test_series_roundtrip(self):
        s = pd.Series({"x": 10, "y": 20, "z": 30}, name="test_series")
        decoded = _decode(_encode(s))
        assert isinstance(decoded, pd.Series)
        pd.testing.assert_series_equal(decoded, s)

    def test_nested_dict_roundtrip(self):
        data = {"level1": {"level2": [1, 2, 3]}}
        assert _decode(_encode(data)) == data

    def test_no_pickle_bytes_in_output(self):
        """确保编码结果是 JSON bytes，不含 pickle magic bytes"""
        raw = _encode({"key": "val"})
        assert not raw.startswith(b"\x80")  # pickle magic byte
        assert raw.startswith(b"{")  # JSON 对象起始


class TestRedisCache:
    """RedisCache 单元测试 — 无真实 Redis 连接"""

    def test_disabled_cache_get_returns_none(self):
        from core.cache import RedisCache
        cache = RedisCache.__new__(RedisCache)
        cache.enabled = False
        cache.client = None
        assert cache.get("any_key") is None

    def test_disabled_cache_set_returns_false(self):
        from core.cache import RedisCache
        cache = RedisCache.__new__(RedisCache)
        cache.enabled = False
        cache.client = None
        assert cache.set("any_key", "value") is False

    def test_disabled_cache_exists_returns_false(self):
        from core.cache import RedisCache
        cache = RedisCache.__new__(RedisCache)
        cache.enabled = False
        cache.client = None
        assert cache.exists("any_key") is False

    def test_ping_returns_false_when_disabled(self):
        from core.cache import RedisCache
        cache = RedisCache.__new__(RedisCache)
        cache.enabled = False
        cache.client = None
        assert cache.ping() is False
