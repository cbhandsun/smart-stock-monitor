"""Add tenant ownership foreign keys and repair legacy orphan owners.

Revision ID: 20260806_0002
Revises: 20260806_0001
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260806_0002"
down_revision = "20260806_0001"
branch_labels = None
depends_on = None

_OWNED_TABLES = (
    ("user_portfolios", "fk_user_portfolios_user_id_users"),
    ("alert_rules", "fk_alert_rules_user_id_users"),
    ("user_activities", "fk_user_activities_user_id_users"),
    ("backtest_results", "fk_backtest_results_user_id_users"),
)


def _foreign_key_exists(table_name: str, constrained_column: str = "user_id") -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(
        constrained_column in (foreign_key.get("constrained_columns") or [])
        and foreign_key.get("referred_table") == "users"
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _foreign_key_name(
    table_name: str, constrained_column: str = "user_id"
) -> str | None:
    for foreign_key in sa.inspect(op.get_bind()).get_foreign_keys(table_name):
        if (
            constrained_column in (foreign_key.get("constrained_columns") or [])
            and foreign_key.get("referred_table") == "users"
        ):
            name = foreign_key.get("name")
            return str(name) if name else None
    return None


def _repair_orphan_users() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    orphan_ids: set[str] = set()
    for table_name, _ in _OWNED_TABLES:
        if table_name not in existing_tables:
            continue
        rows = bind.execute(
            sa.text(
                f"SELECT DISTINCT child.user_id FROM {table_name} child "
                "LEFT JOIN users owner ON owner.id = child.user_id "
                "WHERE child.user_id IS NOT NULL AND owner.id IS NULL"
            )
        )
        orphan_ids.update(str(row[0]) for row in rows if row[0])

    created_at = datetime.now(timezone.utc).isoformat()
    for orphan_id in sorted(orphan_ids):
        suffix = hashlib.sha256(orphan_id.encode("utf-8")).hexdigest()[:16]
        bind.execute(
            sa.text(
                "INSERT INTO users "
                "(id, username, email, password_hash, created_at, preferences, is_active, is_admin) "
                "VALUES (:id, :username, :email, :password_hash, :created_at, :preferences, :is_active, :is_admin)"
            ),
            {
                "id": orphan_id,
                "username": f"legacy_{suffix}",
                "email": f"legacy_{suffix}@invalid.local",
                "password_hash": "!disabled!",
                "created_at": created_at,
                "preferences": "{}",
                "is_active": False,
                "is_admin": False,
            },
        )


def upgrade() -> None:
    _repair_orphan_users()
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name, constraint_name in _OWNED_TABLES:
        if table_name not in existing_tables or _foreign_key_exists(table_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_foreign_key(
                constraint_name,
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table_name, _ in reversed(_OWNED_TABLES):
        if table_name not in existing_tables:
            continue
        constraint_name = _foreign_key_name(table_name)
        if not constraint_name:
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(constraint_name, type_="foreignkey")
