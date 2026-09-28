"""Add shared login throttle state.

Revision ID: 20260806_0004
Revises: 20260806_0003
"""

from alembic import op
import sqlalchemy as sa


revision = "20260806_0004"
down_revision = "20260806_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "login_throttle_states" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "login_throttle_states",
        sa.Column("identity_hash", sa.String(length=64), primary_key=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("blocked_until", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    if "login_throttle_states" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("login_throttle_states")
