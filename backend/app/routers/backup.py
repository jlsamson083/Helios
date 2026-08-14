from fastapi import APIRouter

from app.services.backup_health import get_backup_status


router = APIRouter()


@router.get("/status")
def status():
    return get_backup_status()
