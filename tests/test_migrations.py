"""Upgrade, idempotency, adoption, and rollback tests for Alembic."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from database.models import Base


EXPECTED_TABLES = {
    "users",
    "user_portfolios",
    "alert_rules",
    "notification_deliveries",
    "login_throttle_states",
    "backtest_results",
    "stock_data",
}


def _config(database_url: str) -> Config:
    config = Config("alembic.ini")
    config.attributes["database_url"] = database_url
    return config


def test_migration_upgrades_new_database_and_rolls_back(monkeypatch, tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = _config(url)

    command.upgrade(config, "head")
    command.upgrade(config, "head")
    engine = create_engine(url)
    assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

    command.downgrade(config, "base")
    assert not (EXPECTED_TABLES & set(inspect(engine).get_table_names()))
    engine.dispose()


def test_migration_can_adopt_existing_baseline_schema(monkeypatch, tmp_path: Path):
    url = f"sqlite:///{(tmp_path / 'existing.db').as_posix()}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    monkeypatch.setenv("DATABASE_URL", url)

    command.upgrade(_config(url), "head")

    tables = set(inspect(engine).get_table_names())
    assert EXPECTED_TABLES <= tables
    assert "alembic_version" in tables
    engine.dispose()


def test_migration_repairs_orphan_owner_before_adding_foreign_key(
    monkeypatch, tmp_path: Path
):
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE users ("
            "id VARCHAR(50) PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, "
            "email VARCHAR(100) UNIQUE NOT NULL, password_hash VARCHAR(200) NOT NULL, "
            "created_at VARCHAR(50) NOT NULL, last_login VARCHAR(50), preferences JSON, "
            "is_active BOOLEAN, is_admin BOOLEAN)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE user_portfolios ("
            "id VARCHAR(50) PRIMARY KEY, user_id VARCHAR(50) NOT NULL, name VARCHAR(100) NOT NULL, "
            "description VARCHAR(500), stocks JSON, created_at DATETIME, updated_at DATETIME)"
        )
        connection.exec_driver_sql(
            "INSERT INTO user_portfolios (id, user_id, name, stocks) "
            "VALUES ('legacy_portfolio', 'default_user', '默认自选', '[]')"
        )
    monkeypatch.setenv("DATABASE_URL", url)

    command.upgrade(_config(url), "head")

    with engine.connect() as connection:
        owner = connection.exec_driver_sql(
            "SELECT id, is_active FROM users WHERE id='default_user'"
        ).first()
    assert owner is not None
    assert owner[0] == "default_user"
    assert owner[1] in (False, 0)
    assert any(
        foreign_key.get("referred_table") == "users"
        for foreign_key in inspect(engine).get_foreign_keys("user_portfolios")
    )
    engine.dispose()
