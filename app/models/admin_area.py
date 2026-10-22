from datetime import datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, DateTime, Identity, Index, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AdminArea(Base):
    """An administrative boundary (oblast, raion) or the outline of a city, town or village.

    Settlements have `place` set; their `admin_level` varies (Kyiv 4, Kharkiv 8,
    Lviv 9) or is NULL when the outline is not an administrative boundary (Dnipro).
    """

    __tablename__ = "admin_areas"
    __table_args__ = (
        Index("uq_admin_areas_osm_type_osm_id", "osm_type", "osm_id", unique=True),
        Index("ix_admin_areas_geom", "geom", postgresql_using="gist"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(8))
    osm_id: Mapped[int] = mapped_column(BigInteger)
    admin_level: Mapped[int | None] = mapped_column(SmallInteger)
    place: Mapped[str | None] = mapped_column(String(16))  # city | town | village
    name: Mapped[str | None] = mapped_column(Text)
    name_uk: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    name_ru: Mapped[str | None] = mapped_column(Text)
    geom: Mapped[WKBElement] = mapped_column(
        Geometry("MULTIPOLYGON", srid=4326, spatial_index=False)
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
