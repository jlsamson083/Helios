from fastapi import Depends, FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.auth import require_api_key
from app.core.settings import settings
from app.core.logger import logger
from app.routers.health import router as health_router
from app.routers.energy import router as energy_router
from app.routers.billing import router as billing_router
from app.routers.alerts import router as alerts_router
from app.routers.auth import router as auth_router
from app.routers.cost import router as cost_router

from app.core.database import initialize_database
from app.services.grid_counter_recorder import record_grid_counters
from app.services.cloud_cost import refresh_cost_status

scheduler = AsyncIOScheduler(timezone="Asia/Manila")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    docs_url=None if settings.API_AUTH_REQUIRED else "/docs",
    redoc_url=None if settings.API_AUTH_REQUIRED else "/redoc",
    openapi_url=None if settings.API_AUTH_REQUIRED else "/openapi.json",
)

app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["Health"]
)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])

app.include_router(
    billing_router,
    prefix="/api/v1/billing",
    tags=["Billing"],
    dependencies=[Depends(require_api_key)],
)

app.include_router(
    energy_router,
    prefix="/api/v1/energy",
    tags=["Energy"],
    dependencies=[Depends(require_api_key)],
)

app.include_router(
    alerts_router,
    prefix="/api/v1/alerts",
    tags=["Alerts"],
    dependencies=[Depends(require_api_key)],
)

app.include_router(
    cost_router,
    prefix="/api/v1/cost",
    tags=["Cloud cost"],
    dependencies=[Depends(require_api_key)],
)

@app.get("/", dependencies=[Depends(require_api_key)])
def root():
    return {
        "message": "Welcome to Helios ☀️"
    }

initialize_database()


@app.on_event("startup")
async def start_grid_counter_recorder():
    await record_grid_counters()
    await refresh_cost_status()
    if not scheduler.running:
        scheduler.add_job(
            record_grid_counters,
            "interval",
            minutes=15,
            id="solis-grid-counters",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.add_job(
            refresh_cost_status,
            "interval",
            hours=6,
            id="oci-cloud-cost",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()


@app.on_event("shutdown")
def stop_grid_counter_recorder():
    if scheduler.running:
        scheduler.shutdown(wait=False)

logger.info("Helios API started")
