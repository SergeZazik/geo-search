from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness and database check")
async def health(session: SessionDep) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
    return {"status": "ok"}
