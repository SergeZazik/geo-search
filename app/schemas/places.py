from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.schemas.geojson import FeatureCollection


class BBox(BaseModel):
    min_lon: float = Field(ge=-180, le=180)
    min_lat: float = Field(ge=-90, le=90)
    max_lon: float = Field(ge=-180, le=180)
    max_lat: float = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.min_lon >= self.max_lon or self.min_lat >= self.max_lat:
            raise ValueError("bbox must be min_lon,min_lat,max_lon,max_lat with min < max")
        return self

    @classmethod
    def parse(cls, raw: str) -> Self:
        """Parse "min_lon,min_lat,max_lon,max_lat", the order used by GeoJSON and OGC APIs."""
        parts = raw.split(",")
        if len(parts) != 4:
            raise ValueError("bbox must have 4 comma-separated numbers")
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
        return cls(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat)


class PlaceProperties(BaseModel):
    osm_type: str
    osm_id: int
    osm_url: str
    category: str = Field(examples=["amenity"])
    kind: str = Field(examples=["cafe"])
    name: str | None
    names: dict[str, str] = Field(
        description="Localized names by language code", examples=[{"uk": "Кава", "en": "Coffee"}]
    )
    area_m2: float | None = Field(description="Area for polygons, null for points and lines")
    tags: dict[str, str]


class NearbyPlaceProperties(PlaceProperties):
    distance_m: float


PlaceCollection = FeatureCollection[PlaceProperties]
NearbyPlaceCollection = FeatureCollection[NearbyPlaceProperties]
