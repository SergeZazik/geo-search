from pydantic import BaseModel, Field

from app.schemas.geojson import FeatureCollection
from app.schemas.kinds import Kind
from app.schemas.places import DEFAULT_LIMIT, MAX_LIMIT, MAX_RADIUS_M, PlaceProperties


class SearchFilter(BaseModel):
    """What a plain-language query asks for. The LLM fills it in; the SQL is built from it.

    The field descriptions are part of the JSON schema the LLM gets.
    """

    kinds: list[Kind] = Field(
        default_factory=list,
        description="Types of places to find; several if one word covers several "
        "(where to eat: restaurant, cafe, fast_food). Empty if the query names no type.",
    )
    city: str | None = Field(
        default=None,
        description="City, town or village to search in, in Ukrainian as on the map "
        "(Днепр, Dnipro: Дніпро).",
    )
    near_place: str | None = Field(
        default=None,
        description="Name of the place or street the results must be near, in Ukrainian "
        "as on the map, without words like 'near' (возле набережной: набережна; "
        "на проспекте Яворницкого: проспект Яворницького).",
    )
    radius_m: int | None = Field(
        default=None,
        ge=1,
        le=MAX_RADIUS_M,
        description="Distance from near_place in meters if the query gives one; "
        "100 if the place must be on the street itself (на проспекте, on Main Street).",
    )
    min_area_m2: float | None = Field(
        default=None,
        ge=0,
        description="Minimum area in square meters if the query asks for large places "
        "or gives a size (1 ha = 10000 m2).",
    )

    def is_empty(self) -> bool:
        """True if there is nothing to search for; a radius alone is not a search."""
        return not (self.kinds or self.city or self.near_place or self.min_area_m2)


class SearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=300,
        description="What to find, in Ukrainian, Russian or English",
        examples=["кафе возле набережной в Днепре"],
    )
    limit: int = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)


class SearchMatches(BaseModel):
    """What the names in the filter turned out to be in the data."""

    city: str | None = Field(description="The city the search is limited to")
    near_place: list[str] = Field(
        description="The place or streets distances are measured to: several streets "
        "when a name fits them equally well, as 'набережна' fits every embankment",
    )
    radius_m: int | None = Field(description="Search radius around near_place")


class SearchPlaceProperties(PlaceProperties):
    distance_m: float | None = Field(description="Distance to near_place, null without one")


class SearchResult(FeatureCollection[SearchPlaceProperties]):
    """GeoJSON with two foreign members: how the query was understood and matched."""

    filter: SearchFilter
    matched: SearchMatches
