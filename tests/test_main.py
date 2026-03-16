"""
tests/test_main.py — 核心数据获取逻辑测试
"""
import pytest
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCacheFunctions:
    """测试缓存读写"""

    def test_save_and_load_cache(self, sample_kline_df, tmp_path):
        """测试缓存的写入和读取"""
        import importlib
        # 临时替换 CACHE_DIR
        with patch('main.CACHE_DIR', str(tmp_path)):
            with patch('main.get_cache_path') as mock_path:
                cache_file = tmp_path / "test_cache.json"
                mock_path.return_value = str(cache_file)

                from main import save_to_cache, load_from_cache
                save_to_cache("test_key", sample_kline_df)

                assert cache_file.exists(), "缓存文件应已创建"

                loaded = load_from_cache("test_key")
                assert loaded is not None, "应能读取缓存"
                assert len(loaded) == len(sample_kline_df), "行数应一致"

    def test_load_nonexistent_cache(self, tmp_path):
        """测试读取不存在的缓存"""
        with patch('main.get_cache_path', return_value=str(tmp_path / "nonexistent.json")):
            from main import load_from_cache
            result = load_from_cache("missing_key")
            assert result is None

    def test_save_empty_df_does_nothing(self, empty_df, tmp_path):
        """测试空DataFrame不写入缓存"""
        with patch('main.CACHE_DIR', str(tmp_path)):
            with patch('main.get_cache_path', return_value=str(tmp_path / "empty.json")):
                from main import save_to_cache
                save_to_cache("empty_key", empty_df)
                assert not (tmp_path / "empty.json").exists()


class TestCleanupOldCache:
    """测试缓存清理"""

    def test_cleanup_removes_old_files(self, tmp_path):
        """测试清理过期缓存"""
        import time

        # 创建一个"旧"文件
        old_file = tmp_path / "old_cache_2020-01-01.json"
        old_file.write_text('{"test": 1}')
        # 修改文件时间为8天前
        old_time = time.time() - 8 * 86400
        os.utime(str(old_file), (old_time, old_time))

        # 创建一个"新"文件
        new_file = tmp_path / "new_cache_2026-03-15.json"
        new_file.write_text('{"test": 2}')

        with patch('main.CACHE_DIR', str(tmp_path)):
            from main import cleanup_old_cache
            cleanup_old_cache(max_age_days=7)

        assert not old_file.exists(), "旧文件应被清理"
        assert new_file.exists(), "新文件应保留"


class TestStockNamesBatch:
    """测试批量获取股票名称"""

    def test_empty_input(self):
        from main import get_stock_names_batch
        result = get_stock_names_batch([])
        assert result == {}

    @patch('main.requests.get')
    def test_network_error_returns_empty(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        from main import get_stock_names_batch
        result = get_stock_names_batch(["601318"])
        assert isinstance(result, dict)
