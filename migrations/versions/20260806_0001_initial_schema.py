"""Create the initial Smart Stock Monitor schema.

Revision ID: 20260806_0001
Revises: None
"""

from alembic import op

from database.models import Base


revision = "20260806_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create missing baseline tables for new and existing installations."""
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """Drop the baseline schema in dependency-safe reverse order."""
    Base.metadata.drop_all(bind=op.get_bind(), checkfirst=True)
