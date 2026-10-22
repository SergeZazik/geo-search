from dataclasses import dataclass
from typing import Any

from sqlalchemy import ScalarSelect, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AdminArea
from app.repositories.names import name_matches, name_similarity

NAME_COLUMNS = (AdminArea.name, AdminArea.name_uk, AdminArea.name_en, AdminArea.name_ru)


@dataclass(frozen=True, slots=True)
class AreaMatch:
    id: int
    name: str | None
    place: str | None
    similarity: float


def area_geom(area_id: int) -> ScalarSelect[Any]:
    """The outline of an admin area, for spatial conditions on other tables."""
    return select(AdminArea.geom).where(AdminArea.id == area_id).scalar_subquery()


class AdminAreaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def match_query(phrase: str, limit: int) -> Select[int, str | None, str | None, float]:
        similarity = name_similarity(phrase, NAME_COLUMNS)
        return (
            select(AdminArea.id, AdminArea.name, AdminArea.place, similarity)
            .where(name_matches(phrase, NAME_COLUMNS))
            .order_by(
                similarity.desc(),
                # Equally good names: a settlement before an oblast or a raion,
                # then the largest one, so "Запоріжжя" is the city, not a village.
                AdminArea.place.is_(None),
                func.ST_Area(AdminArea.geom).desc(),
                AdminArea.id,
            )
            .limit(limit)
        )

    async def match(self, phrase: str, limit: int) -> list[AreaMatch]:
        result = await self.session.execute(self.match_query(phrase, limit))
        return [AreaMatch(*row) for row in result]
