"""Create places and admin_areas with spatial indexes.

Revision ID: 0001
Revises:
Create Date: 2026-10-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from geoalchemy2 import Geometry
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _names() -> list[sa.Column[str]]:
    return [sa.Column(column, sa.Text()) for column in ("name", "name_uk", "name_en", "name_ru")]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "places",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("osm_type", sa.String(8), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        *_names(),
        sa.Column("tags", postgresql.JSONB(), nullable=False),
        sa.Column("geom", Geometry(srid=4326, spatial_index=False), nullable=False),
        sa.Column("location", Geometry("POINT", srid=4326, spatial_index=False), nullable=False),
        sa.Column("area_m2", sa.Float(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_places"),
    )
    op.create_index("uq_places_osm_type_osm_id", "places", ["osm_type", "osm_id"], unique=True)
    op.create_index("ix_places_kind", "places", ["kind"])
    op.create_index("ix_places_location", "places", ["location"], postgresql_using="gist")
    op.create_index(
        "ix_places_location_geog",
        "places",
        [sa.text("geography(location)")],
        postgresql_using="gist",
    )

    op.create_table(
        "admin_areas",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("osm_type", sa.String(8), nullable=False),
        sa.Column("osm_id", sa.BigInteger(), nullable=False),
        sa.Column("admin_level", sa.SmallInteger(), nullable=False),
        *_names(),
        sa.Column("geom", Geometry("MULTIPOLYGON", srid=4326, spatial_index=False), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_admin_areas"),
    )
    op.create_index(
        "uq_admin_areas_osm_type_osm_id", "admin_areas", ["osm_type", "osm_id"], unique=True
    )
    op.create_index("ix_admin_areas_geom", "admin_areas", ["geom"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("admin_areas")
    op.drop_table("places")
