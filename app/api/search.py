import logging

from fastapi import APIRouter, HTTPException, status

from app.api.deps import SearchServiceDep
from app.schemas.search import SearchRequest, SearchResult
from app.services.query_parser import QueryNotUnderstoodError, SearchUnavailableError
from app.services.search import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["search"])


@router.post(
    "/search",
    summary="Places for a plain-language query",
    responses={
        404: {"description": "A city or landmark from the query is not in the data"},
        422: {"description": "The query could not be understood"},
        503: {"description": "Plain-language search is off or the LLM is unreachable"},
    },
)
async def search(service: SearchServiceDep, request: SearchRequest) -> SearchResult:
    """An LLM turns the query into a typed filter (`filter` in the response); the
    service finds the city and the landmark by name (`matched`) and queries PostGIS.
    """
    try:
        return await service.search(request.query, request.limit)
    except QueryNotUnderstoodError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Could not understand the query: {exc}"
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except SearchUnavailableError as exc:
        logger.warning("Search unavailable: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Search is unavailable, try again later"
        ) from exc
