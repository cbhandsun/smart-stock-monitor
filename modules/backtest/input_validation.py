"""Boundary validation for user-supplied backtest parameters."""

from __future__ import annotations

import datetime as dt
import math


def parse_symbols(value: object, *, limit: int = 20) -> list[str]:
    if not isinstance(value, str):
        raise ValueError("股票代码格式不正确")
    symbols = list(
        dict.fromkeys(part.strip() for part in value.split(",") if part.strip())
    )
    if not symbols:
        raise ValueError("请至少输入一个股票代码")
    if len(symbols) > limit:
        raise ValueError(f"单次回测最多支持{limit}只股票")
    if any(not symbol.isdigit() or len(symbol) != 6 for symbol in symbols):
        raise ValueError("股票代码必须是6位数字，并使用半角逗号分隔")
    return symbols


def validate_backtest_range(
    start_date: object,
    end_date: object,
    initial_cash: object,
    commission: object,
) -> tuple[dt.date, dt.date, float, float]:
    if not isinstance(start_date, dt.date) or not isinstance(end_date, dt.date):
        raise ValueError("回测日期格式不正确")
    if start_date >= end_date:
        raise ValueError("开始日期必须早于结束日期")
    if (end_date - start_date).days > 3650:
        raise ValueError("单次回测区间不能超过10年")
    if isinstance(initial_cash, bool) or not isinstance(initial_cash, (int, float)):
        raise ValueError("初始资金格式不正确")
    cash = float(initial_cash)
    if not math.isfinite(cash) or not 1_000 <= cash <= 1_000_000_000:
        raise ValueError("初始资金需在1,000至10亿元之间")
    if isinstance(commission, bool) or not isinstance(commission, (int, float)):
        raise ValueError("手续费率格式不正确")
    fee = float(commission)
    if not math.isfinite(fee) or not 0 <= fee <= 0.05:
        raise ValueError("手续费率需在0至5%之间")
    return start_date, end_date, cash, fee
