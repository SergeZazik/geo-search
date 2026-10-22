"""Store settlement outlines in admin_areas.

City limits are not always administrative boundaries in OSM, so admin_level
becomes optional and the place tag (city, town, village) gets its own column.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("admin_areas", sa.Column("place", sa.String(16), nullable=True))
    op.alter_column("admin_areas", "admin_level", existing_type=sa.SmallInteger(), nullable=True)


def downgrade() -> None:
    # Outlines that are not administrative boundaries have no place in the old schema.
    op.execute("DELETE FROM admin_areas WHERE admin_level IS NULL")
    op.alter_column("admin_areas", "admin_level", existing_type=sa.SmallInteger(), nullable=False)
    op.drop_column("admin_areas", "place")
