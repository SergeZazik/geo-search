from pydantic import BaseModel, Field

from app.schemas.kinds import Kind
from app.schemas.places import MAX_RADIUS_M


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
