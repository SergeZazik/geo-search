from datetime import datetime

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import BigInteger, DateTime, Identity, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Place(Base):
    """A point of interest from OpenStreetMap: a node, a way or a multipolygon relation."""

    __tablename__ = "places"
    __table_args__ = (
        Index("uq_places_osm_type_osm_id", "osm_type", "osm_id", unique=True),
        Index("ix_places_kind", "kind"),
        # Bounding-box queries compare geometries in degrees.
        Index("ix_places_location", "location", postgresql_using="gist"),
        # Radius queries work in meters on the geography type. The expression
        # must match the one in PlaceRepository.near(), or the planner skips it.
        Index(
            "ix_places_location_geog",
            text("geography(location)"),
            postgresql_using="gist",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    osm_type: Mapped[str] = mapped_column(String(8))  # node | way | relation
    osm_id: Mapped[int] = mapped_column(BigInteger)
    category: Mapped[str] = mapped_column(String(16))  # amenity | shop | tourism | leisure
    kind: Mapped[str] = mapped_column(String(64))  # the tag value: cafe, park, supermarket...
    name: Mapped[str | None] = mapped_column(Text)
    name_uk: Mapped[str | None] = mapped_column(Text)
    name_en: Mapped[str | None] = mapped_column(Text)
    name_ru: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[dict[str, str]] = mapped_column(JSONB)
    # Full shape: a point for nodes, a line or a multipolygon for ways and relations.
    geom: Mapped[WKBElement] = mapped_column(Geometry(srid=4326, spatial_index=False))
    # Representative point inside the shape, used for all spatial lookups.
    location: Mapped[WKBElement] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    area_m2: Mapped[float | None]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
