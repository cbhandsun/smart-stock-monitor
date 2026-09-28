"""Add recoverable portfolio lifecycle fields.

Revision ID: 20260806_0005
Revises: 20260806_0004
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0005"
down_revision = "20260806_0004"
branch_labels = None
depends_on = None


def _columns() -> set[str]:
    return {
        column["name"]
        for column in sa.inspect(op.get_bind()).get_columns("user_portfolios")
    }


def upgrade() -> None:
    columns = _columns()
    with op.batch_alter_table("user_portfolios") as batch_op:
        if "archived_at" not in columns:
            batch_op.add_column(sa.Column("archived_at", sa.DateTime()))
        if "deleted_at" not in columns:
            batch_op.add_column(sa.Column("deleted_at", sa.DateTime()))


def downgrade() -> None:
    columns = _columns()
    with op.batch_alter_table("user_portfolios") as batch_op:
        if "deleted_at" in columns:
            batch_op.drop_column("deleted_at")
        if "archived_at" in columns:
            batch_op.drop_column("archived_at")
