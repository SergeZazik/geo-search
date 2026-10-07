"""Create streets with spatial and trigram indexes.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-07
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME_COLUMNS = ("name", "name_uk", "name_en", "name_ru")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "streets",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column("highway", sa.String(32), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_uk", sa.Text(), nullable=True),
        sa.Column("name_en", sa.Text(), nullable=True),
        sa.Column("name_ru", sa.Text(), nullable=True),
        sa.Column("geom", Geometry("LINESTRING", srid=4326, spatial_index=False), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_streets"),
    )
    op.create_index("uq_streets_osm_id", "streets", ["osm_id"], unique=True)
    op.create_index("ix_streets_geom", "streets", ["geom"], postgresql_using="gist")
    op.create_index(
        "ix_streets_geom_geog",
        "streets",
        [sa.text("geography(geom)")],
        postgresql_using="gist",
    )
    op.create_index(
        "ix_streets_names_trgm",
        "streets",
        list(NAME_COLUMNS),
        postgresql_using="gin",
        postgresql_ops=dict.fromkeys(NAME_COLUMNS, "gin_trgm_ops"),
    )


def downgrade() -> None:
    # pg_trgm stays installed, like postgis in 0001.
    op.drop_table("streets")
