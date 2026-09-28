"""Regression tests for cross-user portfolio and alert access."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from database.models import DatabaseManager
from modules.alerts.alert_system import AlertManager, AlertStatus, AlertType
from modules.portfolio.watchlist_manager import WatchlistManager


@pytest.fixture
def db_manager(tmp_path: Path, seed_users):
    manager = DatabaseManager(
        f"sqlite:///{(tmp_path / 'tenant.db').as_posix()}", create_schema=True
    )
    seed_users(manager, "user_one", "user_two")
    yield manager
    manager.close()


def test_portfolio_update_cannot_cross_user_boundary(db_manager):
    db_manager.save_portfolio("portfolio_shared", "user_one", "One", "", [])

    with pytest.raises(PermissionError, match="not found"):
        db_manager.save_portfolio("portfolio_shared", "user_two", "Hijacked", "", [])

    owned = db_manager.get_portfolio("portfolio_shared", "user_one")
    assert owned.name == "One"
    assert db_manager.get_portfolio("portfolio_shared", "user_two") is None


def test_portfolio_delete_requires_owner(db_manager):
    db_manager.save_portfolio("portfolio_delete", "user_one", "One", "", [])

    assert db_manager.delete_portfolio("portfolio_delete", "user_two") is False
    assert db_manager.get_portfolio("portfolio_delete", "user_one") is not None
    assert db_manager.delete_portfolio("portfolio_delete", "user_one") is True


def test_portfolio_archive_delete_and_restore_lifecycle(db_manager):
    manager = WatchlistManager(user_id="user_one", db_manager=db_manager)
    portfolio = manager.create_portfolio("Lifecycle")

    assert manager.archive_portfolio(portfolio.id) is True
    assert manager.get_portfolio(portfolio.id) is None
    assert [item.id for item in manager.list_by_state("archived")] == [portfolio.id]

    assert manager.restore_portfolio(portfolio.id) is True
    manager.delete_portfolio(portfolio.id)
    assert [item.id for item in manager.list_by_state("deleted")] == [portfolio.id]
    assert manager.restore_portfolio(portfolio.id) is True
    assert manager.get_portfolio(portfolio.id) is not None


def test_concurrent_stock_additions_do_not_overwrite_each_other(db_manager):
    manager = WatchlistManager(user_id="user_one", db_manager=db_manager)
    portfolio = manager.create_portfolio("Concurrent positions")
    managers = [
        WatchlistManager(user_id="user_one", db_manager=db_manager) for _ in range(12)
    ]

    def add_stock(index):
        managers[index].add_stock(
            portfolio.id,
            f"{index + 1:06d}",
            f"Stock {index}",
        )

    with ThreadPoolExecutor(max_workers=len(managers)) as pool:
        list(pool.map(add_stock, range(len(managers))))

    refreshed = WatchlistManager(user_id="user_one", db_manager=db_manager)
    assert set(refreshed.get_portfolio_symbols(portfolio.id)) == {
        f"{index + 1:06d}" for index in range(len(managers))
    }


def test_concurrent_duplicate_portfolio_names_allow_only_one(db_manager):
    managers = [
        WatchlistManager(user_id="user_one", db_manager=db_manager) for _ in range(8)
    ]

    def create(manager):
        try:
            manager.create_portfolio("Single active name")
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=len(managers)) as pool:
        created = list(pool.map(create, managers))

    assert created.count(True) == 1
    assert created.count(False) == len(managers) - 1


def test_stale_metadata_update_preserves_concurrent_stock_change(db_manager):
    creator = WatchlistManager(user_id="user_one", db_manager=db_manager)
    portfolio = creator.create_portfolio("Metadata race")
    stale_editor = WatchlistManager(user_id="user_one", db_manager=db_manager)
    stock_editor = WatchlistManager(user_id="user_one", db_manager=db_manager)

    stock_editor.add_stock(portfolio.id, "600519", "贵州茅台")
    stale_editor.update_portfolio(portfolio.id, description="updated metadata")

    refreshed = WatchlistManager(user_id="user_one", db_manager=db_manager)
    result = refreshed.get_portfolio(portfolio.id)
    assert result is not None
    assert result.description == "updated metadata"
    assert [stock.symbol for stock in result.stocks] == ["600519"]


def test_stale_manager_can_remove_newly_added_stock(db_manager):
    creator = WatchlistManager(user_id="user_one", db_manager=db_manager)
    portfolio = creator.create_portfolio("Removal race")
    stale_editor = WatchlistManager(user_id="user_one", db_manager=db_manager)
    stock_editor = WatchlistManager(user_id="user_one", db_manager=db_manager)

    stock_editor.add_stock(portfolio.id, "000001", "平安银行")

    assert stale_editor.remove_stock(portfolio.id, "000001") is True
    refreshed = WatchlistManager(user_id="user_one", db_manager=db_manager)
    assert refreshed.get_portfolio_symbols(portfolio.id) == []


def test_watchlist_requires_explicit_authenticated_user_outside_streamlit(db_manager):
    with pytest.raises(ValueError, match="user_id"):
        WatchlistManager(db_manager=db_manager)


def test_alert_read_update_delete_cannot_cross_user_boundary(db_manager):
    owner = AlertManager(user_id="user_one", db_manager=db_manager)
    attacker = AlertManager(user_id="user_two", db_manager=db_manager)
    created = owner.add_alert("600519", AlertType.PRICE_ABOVE, 100.0, "目标价")

    assert attacker.get_alert(created.id) is None
    assert attacker.disable_alert(created.id) is False
    assert attacker.remove_alert(created.id) is False
    assert owner.get_alert(created.id).status is AlertStatus.ACTIVE
    assert owner.remove_alert(created.id) is True


def test_alert_trigger_is_inclusive_and_percent_drop_uses_negative_threshold(
    db_manager,
):
    manager = AlertManager(user_id="user_one", db_manager=db_manager)
    price = manager.add_alert("600519", AlertType.PRICE_ABOVE, 100.0)
    drop = manager.add_alert("000001", AlertType.CHANGE_PCT_BELOW, 5.0)

    price_hits = manager.check_alerts("600519", {"price": 100.0})
    drop_hits = manager.check_alerts("000001", {"change_pct": -5.0})

    assert [alert.id for alert in price_hits] == [price.id]
    assert [alert.id for alert in drop_hits] == [drop.id]


@pytest.mark.parametrize(
    ("symbol", "threshold"),
    [("ABC", 1.0), ("600519", float("nan")), ("600519", float("inf"))],
)
def test_alert_input_validation_rejects_invalid_values(db_manager, symbol, threshold):
    manager = AlertManager(user_id="user_one", db_manager=db_manager)
    with pytest.raises(ValueError):
        manager.add_alert(symbol, AlertType.PRICE_ABOVE, threshold)
