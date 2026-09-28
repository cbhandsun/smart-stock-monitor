"""Tests for authenticated watchlist persistence without shared file fallback."""

from pathlib import Path

import pytest

import database.models as models
import pages


@pytest.fixture
def isolated_db(tmp_path: Path, seed_users):
    manager = models.DatabaseManager(
        f"sqlite:///{(tmp_path / 'watchlist.db').as_posix()}",
        create_schema=True,
    )
    models.db_manager = manager
    seed_users(manager, "user_one", "user_two")
    yield manager
    manager.close()
    models.db_manager = None


def test_watchlists_are_isolated_by_authenticated_user(monkeypatch, isolated_db):
    active_user = {"id": "user_one"}
    monkeypatch.setattr(pages, "require_user_id", lambda: active_user["id"])

    pages.save_watchlist(["600519", "000001", "600519"])
    assert pages.load_watchlist() == ["600519", "000001"]

    active_user["id"] = "user_two"
    assert pages.load_watchlist() == []
    pages.save_watchlist(["300750"])
    assert pages.load_watchlist() == ["300750"]

    active_user["id"] = "user_one"
    assert pages.load_watchlist() == ["600519", "000001"]


@pytest.mark.parametrize("stocks", [None, ["ABC"], ["60051"], ["600519"] * 501])
def test_watchlist_rejects_invalid_or_extreme_input(monkeypatch, isolated_db, stocks):
    monkeypatch.setattr(pages, "require_user_id", lambda: "user_one")
    with pytest.raises(ValueError):
        pages.save_watchlist(stocks)
