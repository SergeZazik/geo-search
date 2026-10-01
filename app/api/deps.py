from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.places import PlaceRepository
from app.services.places import PlaceService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_place_service(session: SessionDep) -> PlaceService:
    return PlaceService(PlaceRepository(session))


PlaceServiceDep = Annotated[PlaceService, Depends(get_place_service)]
