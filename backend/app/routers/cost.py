from fastapi import APIRouter

from app.services.cloud_cost import get_cost_status, refresh_cost_status


router = APIRouter()


@router.get("/status")
def status():
    return get_cost_status()


@router.post("/refresh")
async def refresh():
    return await refresh_cost_status()
