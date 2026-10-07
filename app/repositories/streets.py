from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminArea, Street

NAME_COLUMNS = (Street.name, Street.name_uk, Street.name_en, Street.name_ru)


@dataclass(frozen=True, slots=True)
class StreetMatch:
    name: str
    similarity: float


def _in_area(area_id: int) -> ColumnElement[bool]:
    area = select(AdminArea.geom).where(AdminArea.id == area_id).scalar_subquery()
    return func.ST_Intersects(Street.geom, area)


def street_segments(name: str, area_id: int | None = None) -> Select[Any]:
    """Every way of the street with this name, only inside the admin area if one is given.

    Without an area, "вулиця Шевченка" means the streets of that name in every city.
    """
    query = select(Street.geom).where(Street.name == name)
    if area_id is not None:
        query = query.where(_in_area(area_id))
    return query


class StreetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def match_query(phrase: str, limit: int, area_id: int | None = None) -> Select[str, Any]:
        # name %> phrase means word_similarity(phrase, name) >= 0.6 (the pg_trgm default):
        # the phrase is compared with the best-matching part of the name, so
        # "набережная" finds "Січеславська набережна". With the column on the left,
        # ix_streets_names_trgm serves the condition.
        matches = or_(*(column.op("%>", is_comparison=True)(phrase) for column in NAME_COLUMNS))
        # GREATEST skips NULLs, so a missing translation does not hide a match.
        similarity = func.max(
            func.greatest(*(func.word_similarity(phrase, column) for column in NAME_COLUMNS))
        )
        query = select(Street.name, similarity).where(matches)
        if area_id is not None:
            query = query.where(_in_area(area_id))
        # One row per street, not per way.
        return query.group_by(Street.name).order_by(similarity.desc(), Street.name).limit(limit)

    async def match(self, phrase: str, limit: int, area_id: int | None = None) -> list[StreetMatch]:
        result = await self.session.execute(self.match_query(phrase, limit, area_id))
        return [StreetMatch(name, similarity) for name, similarity in result]
