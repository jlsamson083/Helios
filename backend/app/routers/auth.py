import hashlib
import json
import secrets
from datetime import datetime, timezone
from hmac import compare_digest

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers.structs import (
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.auth import require_api_key
from app.core.database import get_connection
from app.core.settings import settings


router = APIRouter()
registration_challenges = {}
authentication_challenges = {}


class LoginRequest(BaseModel):
    username: str
    password: str


class CredentialResponse(BaseModel):
    challenge_token: str
    credential: dict


def _set_session(response: Response) -> None:
    response.set_cookie(
        "helios_session", settings.HELIOS_SESSION_SECRET,
        max_age=31_536_000, secure=True, httponly=True,
        samesite="strict", path="/",
    )


def verify_password(password: str, encoded_hash: str) -> bool:
    try:
        salt, expected = encoded_hash.split("$", 1)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 200_000
    ).hex()
    return compare_digest(actual, expected)


@router.post("/login", status_code=204)
def login(credentials: LoginRequest, response: Response):
    connection = get_connection()
    try:
        account = connection.execute(
            "SELECT password_hash FROM user_accounts WHERE username = ?",
            (credentials.username.strip(),),
        ).fetchone()
    finally:
        connection.close()
    valid = account is not None and verify_password(
        credentials.password, account["password_hash"]
    )
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    _set_session(response)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(
        "helios_session", path="/", secure=True, httponly=True, samesite="strict"
    )


@router.post("/passkey/register/options", dependencies=[Depends(require_api_key)])
def passkey_registration_options():
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name="Helios Home Energy",
        user_id=b"helios-family",
        user_name="helios",
        user_display_name="Helios Family",
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    token = secrets.token_urlsafe(24)
    registration_challenges[token] = options.challenge
    return {"challenge_token": token, "options": json.loads(options_to_json(options))}


@router.post("/passkey/register/verify", status_code=204,
             dependencies=[Depends(require_api_key)])
def verify_passkey_registration(body: CredentialResponse):
    challenge = registration_challenges.pop(body.challenge_token, None)
    if challenge is None:
        raise HTTPException(status_code=400, detail="Registration challenge expired")
    try:
        verified = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            require_user_verification=True,
        )
    except Exception:
        raise HTTPException(status_code=400, detail="Face ID registration failed")
    connection = get_connection()
    try:
        connection.execute(
            """INSERT OR REPLACE INTO passkey_credentials
               (credential_id, public_key, sign_count, created_at)
               VALUES (?, ?, ?, ?)""",
            (body.credential["id"], verified.credential_public_key,
             verified.sign_count, datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()


@router.post("/passkey/authenticate/options")
def passkey_authentication_options():
    connection = get_connection()
    try:
        rows = connection.execute("SELECT credential_id FROM passkey_credentials").fetchall()
    finally:
        connection.close()
    if not rows:
        raise HTTPException(status_code=404, detail="No Face ID passkey enrolled")
    from webauthn import base64url_to_bytes
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(row[0])) for row in rows],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    token = secrets.token_urlsafe(24)
    authentication_challenges[token] = options.challenge
    return {"challenge_token": token, "options": json.loads(options_to_json(options))}


@router.post("/passkey/authenticate/verify", status_code=204)
def verify_passkey_authentication(body: CredentialResponse, response: Response):
    challenge = authentication_challenges.pop(body.challenge_token, None)
    if challenge is None:
        raise HTTPException(status_code=400, detail="Authentication challenge expired")
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM passkey_credentials WHERE credential_id = ?",
            (body.credential["id"],),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=401, detail="Unknown passkey")
        try:
            verified = verify_authentication_response(
                credential=body.credential, expected_challenge=challenge,
                expected_rp_id=settings.WEBAUTHN_RP_ID,
                expected_origin=settings.WEBAUTHN_ORIGIN,
                credential_public_key=row["public_key"],
                credential_current_sign_count=row["sign_count"],
                require_user_verification=True,
            )
        except Exception:
            raise HTTPException(status_code=401, detail="Face ID authentication failed")
        connection.execute(
            "UPDATE passkey_credentials SET sign_count = ? WHERE credential_id = ?",
            (verified.new_sign_count, row["credential_id"]),
        )
        connection.commit()
    finally:
        connection.close()
    _set_session(response)
