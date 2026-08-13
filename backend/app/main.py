from fastapi import FastAPI

from app.core.settings import settings
from app.core.logger import logger
from app.routers.health import router as health_router
from app.routers.energy import router as energy_router

from app.core.database import initialize_database

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION
)

app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["Health"]
)

app.include_router(
    energy_router,
    prefix="/api/v1/energy",
    tags=["Energy"]
)

@app.get("/")
def root():
    return {
        "message": "Welcome to Helios ☀️"
    }

initialize_database()

logger.info("Helios API started")