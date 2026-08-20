import base64
import hashlib
import hmac
from hmac import compare_digest
from typing import Optional

from fastapi import Cookie, Header, HTTPException, status

from app.core.settings import settings


def create_session_token(username: str) -> str:
    payload = base64.urlsafe_b64encode(username.encode()).decode().rstrip("=")
    signature = hmac.new(
        settings.HELIOS_SESSION_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"v1.{payload}.{signature}"


def session_username(token: Optional[str]) -> Optional[str]:
    if not token or not settings.HELIOS_SESSION_SECRET:
        return None
    try:
        version, payload, signature = token.split(".", 2)
        if version != "v1":
            return None
        expected = hmac.new(
            settings.HELIOS_SESSION_SECRET.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not compare_digest(signature, expected):
            return None
        padding = "=" * (-len(payload) % 4)
        return base64.urlsafe_b64decode(payload + padding).decode()
    except (ValueError, UnicodeDecodeError):
        return None


def authenticated_username(
    x_helios_key: Optional[str],
    helios_session: Optional[str],
) -> Optional[str]:
    if bool(x_helios_key) and compare_digest(x_helios_key, settings.HELIOS_API_KEY):
        return settings.HELIOS_OWNER_USERNAME
    return session_username(helios_session)


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
    signed_session_valid = session_username(helios_session) is not None
    legacy_session_valid = bool(
        helios_session and settings.HELIOS_SESSION_SECRET
    ) and compare_digest(helios_session, settings.HELIOS_SESSION_SECRET)
    session_valid = signed_session_valid or legacy_session_valid
    if not api_key_valid and not session_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Helios API key",
        )


def require_authenticated_username(
    x_helios_key: Optional[str] = Header(default=None),
    helios_session: Optional[str] = Cookie(default=None),
) -> str:
    if not settings.API_AUTH_REQUIRED:
        return settings.HELIOS_OWNER_USERNAME
    username = authenticated_username(x_helios_key, helios_session)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return username


def require_owner(
    x_helios_key: Optional[str] = Header(default=None),
    helios_session: Optional[str] = Cookie(default=None),
) -> str:
    username = require_authenticated_username(x_helios_key, helios_session)
    if username.casefold() != settings.HELIOS_OWNER_USERNAME.casefold():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Owner access required",
        )
    return username
