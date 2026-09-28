"""Add durable notification delivery ledger.

Revision ID: 20260806_0003
Revises: 20260806_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0003"
down_revision = "20260806_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "notification_deliveries" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "notification_deliveries",
        sa.Column("event_key", sa.String(length=120), primary_key=True),
        sa.Column("alert_id", sa.String(length=50), nullable=False),
        sa.Column("user_id", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("channel", sa.String(length=20)),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=50)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_notification_deliveries_alert_id", "notification_deliveries", ["alert_id"]
    )
    op.create_index(
        "ix_notification_deliveries_user_id", "notification_deliveries", ["user_id"]
    )


def downgrade() -> None:
    if "notification_deliveries" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index(
        "ix_notification_deliveries_user_id", table_name="notification_deliveries"
    )
    op.drop_index(
        "ix_notification_deliveries_alert_id", table_name="notification_deliveries"
    )
    op.drop_table("notification_deliveries")
