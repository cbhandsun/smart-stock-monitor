"""Boundary and ownership tests for persisted backtests."""

import datetime as dt
from pathlib import Path

import pytest

from database.models import DatabaseManager
from modules.backtest.input_validation import parse_symbols, validate_backtest_range


@pytest.mark.parametrize("value", [None, "", "600519,ABC", "60051", ",,,"])
def test_backtest_symbols_reject_invalid_inputs(value):
    with pytest.raises(ValueError):
        parse_symbols(value)


def test_backtest_symbols_are_deduplicated_and_bounded():
    assert parse_symbols("600519, 000001,600519") == ["600519", "000001"]
    with pytest.raises(ValueError, match="最多"):
        parse_symbols(",".join(f"{index:06d}" for index in range(21)))


@pytest.mark.parametrize(
    ("start", "end", "cash", "fee"),
    [
        (dt.date(2025, 1, 1), dt.date(2025, 1, 1), 100_000, 0.001),
        (dt.date(2000, 1, 1), dt.date(2025, 1, 1), 100_000, 0.001),
        (dt.date(2024, 1, 1), dt.date(2025, 1, 1), float("nan"), 0.001),
        (dt.date(2024, 1, 1), dt.date(2025, 1, 1), 100_000, 0.1),
    ],
)
def test_backtest_range_rejects_invalid_or_extreme_values(start, end, cash, fee):
    with pytest.raises(ValueError):
        validate_backtest_range(start, end, cash, fee)


def test_backtest_history_is_always_scoped_to_owner(tmp_path: Path, seed_users):
    db = DatabaseManager(
        f"sqlite:///{(tmp_path / 'backtests.db').as_posix()}", create_schema=True
    )
    seed_users(db, "user_one", "user_two")
    values = [{"date": "2025-01-01", "total_value": 100_000}]
    for user_id in ("user_one", "user_two"):
        db.save_backtest_result(
            result_id=f"backtest_{user_id}",
            user_id=user_id,
            strategy_name="均线交叉",
            symbols={"list": ["600519"]},
            start_date=dt.datetime(2024, 1, 1),
            end_date=dt.datetime(2025, 1, 1),
            initial_cash=100_000,
            final_value=110_000,
            total_return=10.0,
            annual_return=10.0,
            max_drawdown=-5.0,
            sharpe_ratio=1.0,
            total_trades=2,
            daily_values=values,
        )

    assert [item.user_id for item in db.get_backtest_results("user_one")] == [
        "user_one"
    ]
    with pytest.raises(ValueError, match="user_id"):
        db.get_backtest_results("")
    db.close()
