from fastapi import APIRouter

from app.api.v1.routes import portfolios, scenarios, valuations

api_router = APIRouter()
api_router.include_router(portfolios.router)
api_router.include_router(valuations.router)
api_router.include_router(scenarios.router)
