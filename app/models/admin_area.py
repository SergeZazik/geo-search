from datetime import datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, DateTime, Identity, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminArea(Base):
    """An administrative boundary: oblast (level 4), raion (6) or city/town/village (8)."""

    __tablename__ = "admin_areas"
    __table_args__ = (
        Index("uq_admin_areas_osm_type_osm_id", "osm_type", "osm_id", unique=True),
        Index("ix_admin_areas_geom", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(8))
    osm_id: Mapped[int] = mapped_column(BigInteger)
    admin_level: Mapped[int] = mapped_column(SmallInteger)
    name: Mapped[str | None] = mapped_column(Text)
    name_uk: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    name_ru: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
