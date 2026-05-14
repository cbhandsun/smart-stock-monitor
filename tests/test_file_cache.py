"""
tests/test_file_cache.py — 文件缓存读写测试
"""
import sys
import os
import tempfile
import pytest
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_cache_dir(monkeypatch, tmp_path):
    """将 CACHE_DIR 重定向到临时目录，保证测试隔离"""
    import core.file_cache as fc
    monkeypatch.setattr(fc, "CACHE_DIR", str(tmp_path))
    return tmp_path


class TestFileCacheRoundtrip:
    def test_save_and_load(self, tmp_cache_dir):
        from core.file_cache import save_to_cache, load_from_cache
        df = pd.DataFrame({"收盘": [10.0, 11.0, 12.0], "日期": ["20240101", "20240102", "20240103"]})
        save_to_cache("test_key", df)
        loaded = load_from_cache("test_key")
        assert loaded is not None
        assert list(loaded.columns) == list(df.columns)
        assert len(loaded) == len(df)

    def test_load_missing_key_returns_none(self, tmp_cache_dir):
        from core.file_cache import load_from_cache
        assert load_from_cache("nonexistent_key") is None

    def test_save_empty_df_skips_file(self, tmp_cache_dir):
        from core.file_cache import save_to_cache, load_from_cache
        save_to_cache("empty_test", pd.DataFrame())
        assert load_from_cache("empty_test") is None

    def test_save_none_skips_file(self, tmp_cache_dir):
        from core.file_cache import save_to_cache, load_from_cache
        save_to_cache("none_test", None)
        assert load_from_cache("none_test") is None

    def test_cleanup_removes_old_files(self, tmp_cache_dir, monkeypatch):
        import time
        from core.file_cache import save_to_cache, cleanup_old_cache
        import core.file_cache as fc

        df = pd.DataFrame({"x": [1, 2, 3]})
        save_to_cache("old_key", df)

        # 伪造文件修改时间为 10 天前
        cache_files = list(tmp_cache_dir.glob("*.json"))
        assert len(cache_files) == 1
        old_time = time.time() - 10 * 86400
        os.utime(str(cache_files[0]), (old_time, old_time))

        removed = cleanup_old_cache(max_age_days=7)
        assert removed == 1
        assert not cache_files[0].exists()


class TestFileCacheTTL:
    def test_non_trading_hours_uses_full_day_cache(self, tmp_cache_dir, monkeypatch):
        """非交易时段：文件创建后应可以正常读取（无 5min TTL 限制）"""
        import datetime
        from core.file_cache import save_to_cache, load_from_cache

        # 模拟凌晨 3 点（非交易时段）
        fake_now = datetime.datetime(2024, 1, 2, 3, 0, 0)  # 星期二 03:00
        monkeypatch.setattr("core.file_cache.datetime", type("dt", (), {
            "datetime": type("datetime_class", (), {
                "now": staticmethod(lambda: fake_now),
                "strftime": lambda self, fmt: fake_now.strftime(fmt),
            })(),
            "time": datetime.time,
        })())

        df = pd.DataFrame({"收盘": [10.0, 11.0]})
        save_to_cache("night_key", df)
        loaded = load_from_cache("night_key")
        assert loaded is not None
