from hmac import compare_digest
from typing import Optional

from fastapi import Header, HTTPException, status

from app.core.settings import settings


def require_api_key(
    x_helios_key: Optional[str] = Header(default=None),
) -> None:
    """Protect private Helios routes with a timing-safe shared-key check."""
    if not settings.API_AUTH_REQUIRED:
        return

    if x_helios_key is None or not compare_digest(
        x_helios_key,
        settings.HELIOS_API_KEY,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Helios API key",
        )
