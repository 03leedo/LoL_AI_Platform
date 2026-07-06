from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import database_ping

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, object]:
    settings = get_settings()
    db_ok = await database_ping()

    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "database": "ok" if db_ok else "unavailable",
        "riot_api": "configured" if settings.riot_api_key else "missing_key",
    }
