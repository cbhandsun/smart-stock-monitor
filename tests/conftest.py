"""
tests/conftest.py — 共享测试 fixtures
"""

import os

import pytest
import pandas as pd
import numpy as np


os.environ.setdefault(
    "JWT_SECRET_KEY", "test-only-secret-key-that-is-longer-than-32-characters"
)


@pytest.fixture
def seed_users():
    """Insert inactive test owners without depending on authentication flows."""

    def _seed(db_manager, *user_ids):
        from database.models import User

        session = db_manager.get_session()
        try:
            for user_id in user_ids:
                session.add(
                    User(
                        id=user_id,
                        username=f"name_{user_id}",
                        email=f"{user_id}@example.invalid",
                        password_hash="!test-only!",
                        created_at="2026-08-06T00:00:00+00:00",
                        preferences={},
                        is_active=False,
                        is_admin=False,
                    )
                )
            session.commit()
        finally:
            session.close()

    return _seed


@pytest.fixture
def sample_kline_df():
    """生成模拟K线数据的fixture"""
    np.random.seed(42)
    n = 60
    dates = pd.date_range(end="2026-03-15", periods=n, freq="B")
    base_price = 100.0
    returns = np.random.normal(0.001, 0.02, n)
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame(
        {
            "日期": dates.strftime("%Y-%m-%d"),
            "开盘": prices * (1 + np.random.uniform(-0.01, 0.01, n)),
            "最高": prices * (1 + np.random.uniform(0, 0.03, n)),
            "最低": prices * (1 - np.random.uniform(0, 0.03, n)),
            "收盘": prices,
            "成交量": np.random.randint(100000, 1000000, n).astype(float),
        }
    )
    return df


@pytest.fixture
def empty_df():
    """空的DataFrame"""
    return pd.DataFrame()


@pytest.fixture
def small_df(sample_kline_df):
    """仅5行的DataFrame，用于测试数据不足场景"""
    return sample_kline_df.head(5)
