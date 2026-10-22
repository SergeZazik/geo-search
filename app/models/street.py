from datetime import datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, DateTime, Identity, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import NAME_COLUMNS, NAMES_TRGM_OPS, Base


class Street(Base):
    """A named road segment: one OSM way. A street is usually split into many ways."""

    __tablename__ = "streets"
    __table_args__ = (
        Index("uq_streets_osm_id", "osm_id", unique=True),
        Index("ix_streets_geom", "geom", postgresql_using="gist"),
        # Radius queries in meters; the expression must match the one in the queries.
        Index("ix_streets_geom_geog", text("geography(geom)"), postgresql_using="gist"),
        Index(
            "ix_streets_names_trgm",
            *NAME_COLUMNS,
            postgresql_using="gin",
            postgresql_ops=NAMES_TRGM_OPS,
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    osm_id: Mapped[int] = mapped_column(BigInteger)
    highway: Mapped[str] = mapped_column(String(32))  # primary, residential, pedestrian...
    name: Mapped[str] = mapped_column(Text)
    name_uk: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    name_ru: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[WKBElement] = mapped_column(Geometry("LINESTRING", srid=4326, spatial_index=False))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
