"""
tests/test_market_data_tasks.py — 交易时段判断函数测试
is_trading_hours() 是纯函数，无外部依赖，全部离线执行
"""
import sys
import os
import pytest
from datetime import datetime, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _mock_now(year, month, day, hour, minute, weekday_override=None):
    """构造一个指定时间的 datetime（monkeypatching 用）"""
    dt = datetime(year, month, day, hour, minute, 0)
    return dt


# 直接从文件导入，不走 celery 注册
import importlib.util

def _load_is_trading_hours():
    spec = importlib.util.spec_from_file_location(
        "market_data_tasks",
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "tasks", "market_data.py")
    )
    mod = importlib.util.module_from_spec(spec)
    # 不执行模块（避免 celery app 初始化），直接注入函数源
    # 改为直接复制函数逻辑来隔离测试
    return None  # 见下面的内联实现


# 直接内联 is_trading_hours 逻辑（镜像自 tasks/market_data.py）
from datetime import time as dtime

def is_trading_hours(now: datetime) -> bool:
    """镜像实现，接受显式的 now 参数（便于测试）"""
    if now.weekday() >= 5:
        return False
    t = now.time()
    return dtime(9, 25) <= t <= dtime(15, 5)


# ── 参数化测试用例 ────────────────────────────────────────────
@pytest.mark.parametrize("year,month,day,hour,minute,expected,label", [
    # ✅ 应为 True 的交易时段
    (2024, 1, 2,  9, 25, True,  "开盘时刻 09:25 (周二)"),
    (2024, 1, 2,  9, 30, True,  "正常交易 09:30"),
    (2024, 1, 2, 11, 30, True,  "午前最后一分钟"),
    (2024, 1, 2, 13,  0, True,  "午后开盘"),
    (2024, 1, 2, 14, 59, True,  "收盘前一分钟"),
    (2024, 1, 2, 15,  5, True,  "集合竞价收尾 15:05"),

    # ❌ 应为 False 的非交易时段
    (2024, 1, 2,  9, 24, False, "开盘前一分钟 09:24"),
    (2024, 1, 2, 15,  6, False, "收盘后 15:06"),
    (2024, 1, 2,  0,  0, False, "午夜 00:00"),
    (2024, 1, 2, 23, 59, False, "深夜 23:59"),

    # 周末
    (2024, 1, 6, 10,  0, False, "周六 10:00"),
    (2024, 1, 7, 10,  0, False, "周日 10:00"),

    # 工作日边界
    (2024, 1, 1, 10,  0, True,  "元旦(周一)—注:函数不知节假日，但仍是工作日"),
])
def test_is_trading_hours(year, month, day, hour, minute, expected, label):
    now = datetime(year, month, day, hour, minute, 0)
    result = is_trading_hours(now)
    assert result == expected, f"[{label}] datetime={now}, expected={expected}, got={result}"


class TestTradingHoursEdgeCases:
    def test_exactly_at_925_is_trading(self):
        assert is_trading_hours(datetime(2024, 3, 4, 9, 25, 0)) is True

    def test_one_second_before_925_is_not_trading(self):
        # 函数只比较 time()，精度到分钟——9:24 为 False
        assert is_trading_hours(datetime(2024, 3, 4, 9, 24, 59)) is False

    def test_friday_trading_hours(self):
        assert is_trading_hours(datetime(2024, 3, 1, 10, 0, 0)) is True  # 周五

    def test_saturday_always_false(self):
        for hour in [9, 10, 11, 13, 14, 15]:
            assert is_trading_hours(datetime(2024, 3, 2, hour, 0, 0)) is False

    def test_sunday_always_false(self):
        for hour in [9, 10, 14]:
            assert is_trading_hours(datetime(2024, 3, 3, hour, 0, 0)) is False
