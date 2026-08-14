from hmac import compare_digest
from typing import Optional

from fastapi import Cookie, Header, HTTPException, status

from app.core.settings import settings


def require_api_key(
    x_helios_key: Optional[str] = Header(default=None),
    helios_session: Optional[str] = Cookie(default=None),
) -> None:
    """Protect private Helios routes with a timing-safe shared-key check."""
    if not settings.API_AUTH_REQUIRED:
        return

    api_key_valid = bool(x_helios_key) and compare_digest(
        x_helios_key, settings.HELIOS_API_KEY
    )
    session_valid = bool(
        helios_session and settings.HELIOS_SESSION_SECRET
    ) and compare_digest(helios_session, settings.HELIOS_SESSION_SECRET)
    if not api_key_valid and not session_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Helios API key",
        )
