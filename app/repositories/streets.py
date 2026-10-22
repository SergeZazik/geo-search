from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Street
from app.repositories.admin_areas import area_geom
from app.repositories.names import name_matches, name_similarity

NAME_COLUMNS = (Street.name, Street.name_uk, Street.name_en, Street.name_ru)


@dataclass(frozen=True, slots=True)
class StreetMatch:
    name: str
    similarity: float


def street_segments(names: Sequence[str], area_id: int | None = None) -> Select[Any]:
    """Every way of the streets with these names, only inside the admin area if one is given.

    Without an area, "вулиця Шевченка" means the streets of that name in every city.
    """
    query = select(Street.geom).where(Street.name.in_(names))
    if area_id is not None:
        query = query.where(func.ST_Intersects(Street.geom, area_geom(area_id)))
    return query


class StreetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def match_query(phrase: str, limit: int, area_id: int | None = None) -> Select[str, Any]:
        similarity = func.max(name_similarity(phrase, NAME_COLUMNS))
        query = select(Street.name, similarity).where(name_matches(phrase, NAME_COLUMNS))
        if area_id is not None:
            query = query.where(func.ST_Intersects(Street.geom, area_geom(area_id)))
        # One row per street, not per way.
        return query.group_by(Street.name).order_by(similarity.desc(), Street.name).limit(limit)

    async def match(self, phrase: str, limit: int, area_id: int | None = None) -> list[StreetMatch]:
        result = await self.session.execute(self.match_query(phrase, limit, area_id))
        return [StreetMatch(name, similarity) for name, similarity in result]
