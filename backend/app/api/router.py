from fastapi import APIRouter

from app.api.routes import health, live, riot

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(riot.router, prefix="/riot", tags=["riot"])
api_router.include_router(live.router, prefix="/live", tags=["live"])
