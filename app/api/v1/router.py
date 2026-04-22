from fastapi import APIRouter

from app.api.v1.endpoints import health, lgd

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(lgd.router, prefix="/lgd", tags=["lgd"])
