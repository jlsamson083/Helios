from fastapi import APIRouter

from app.core.settings import settings

router = APIRouter()

@router.get("/health")
def health():
    return {
        "status": "healthy",
        "project": settings.APP_NAME,
        "version": settings.VERSION
    }