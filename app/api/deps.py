from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.admin_areas import AdminAreaRepository
from app.repositories.places import PlaceRepository
from app.repositories.streets import StreetRepository
from app.services.places import PlaceService
from app.services.query_parser import QueryParser
from app.services.search import SearchService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_place_service(session: SessionDep) -> PlaceService:
    return PlaceService(PlaceRepository(session))


PlaceServiceDep = Annotated[PlaceService, Depends(get_place_service)]


def get_search_service(request: Request, session: SessionDep) -> SearchService:
    parser: QueryParser | None = request.app.state.query_parser
    if parser is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Plain-language search is off: OPENAI_API_KEY is not set",
        )
    return SearchService(
        parser, PlaceRepository(session), StreetRepository(session), AdminAreaRepository(session)
    )


SearchServiceDep = Annotated[SearchService, Depends(get_search_service)]
