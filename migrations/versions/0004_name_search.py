"""Trigram indexes for finding cities and landmarks by name.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_COLUMNS = ("name", "name_uk", "name_en", "name_ru")


def upgrade() -> None:
    # pg_trgm is installed by 0002.
    for table in ("admin_areas", "places"):
        op.create_index(
            f"ix_{table}_names_trgm",
            table,
            list(NAME_COLUMNS),
            postgresql_using="gin",
            postgresql_ops=dict.fromkeys(NAME_COLUMNS, "gin_trgm_ops"),
        )


def downgrade() -> None:
    op.drop_index("ix_places_names_trgm", table_name="places")
    op.drop_index("ix_admin_areas_names_trgm", table_name="admin_areas")
