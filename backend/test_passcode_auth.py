import hashlib
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.core.auth import create_session_token
from app.core.database import get_connection
from app.main import app


class AccountAuthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        salt = "00" * 16
        digest = hashlib.pbkdf2_hmac(
            "sha256", b"12345678", bytes.fromhex(salt), 200_000
        ).hex()
        connection = get_connection()
        try:
            connection.execute(
                "INSERT OR REPLACE INTO user_accounts (username, password_hash, created_at) VALUES (?, ?, ?)",
                ("TestUser", f"{salt}${digest}", "2026-08-14T00:00:00+00:00"),
            )
            connection.commit()
        finally:
            connection.close()
        self.settings = patch.multiple(
            settings,
            API_AUTH_REQUIRED=True,
            HELIOS_API_KEY="api-secret",
            HELIOS_SESSION_SECRET="session-secret",
        )

    def tearDown(self) -> None:
        connection = get_connection()
        try:
            connection.execute("DELETE FROM user_accounts WHERE username = ?", ("TestUser",))
            connection.commit()
        finally:
            connection.close()

    def test_valid_account_sets_secure_session(self) -> None:
        with self.settings:
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "testuser", "password": "12345678"},
            )
        self.assertEqual(response.status_code, 204)
        self.assertIn("HttpOnly", response.headers["set-cookie"])
        self.assertIn("Secure", response.headers["set-cookie"])

    def test_invalid_password_is_rejected(self) -> None:
        with self.settings:
            response = self.client.post(
                "/api/v1/auth/login",
                json={"username": "TestUser", "password": "00000000"},
            )
        self.assertEqual(response.status_code, 401)

    def test_logout_clears_session_cookie(self) -> None:
        response = self.client.post("/api/v1/auth/logout")
        self.assertEqual(response.status_code, 204)
        self.assertIn("helios_session=", response.headers["set-cookie"])
        self.assertIn("Max-Age=0", response.headers["set-cookie"])

    def test_session_cookie_authenticates_private_api(self) -> None:
        with self.settings:
            response = self.client.get(
                "/api/v1/alerts",
                cookies={"helios_session": "session-secret"},
            )
        self.assertEqual(response.status_code, 200)

    def test_login_session_preserves_account_identity(self) -> None:
        with self.settings:
            token = create_session_token("TestUser")
            response = self.client.get(
                "/api/v1/auth/me",
                cookies={"helios_session": token},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"username": "TestUser", "role": "member"})

    def test_passkey_enrollment_requires_session(self) -> None:
        with self.settings:
            response = self.client.post(
                "/api/v1/auth/passkey/register/options"
            )
        self.assertEqual(response.status_code, 401)

    def test_authenticated_passkey_options_require_face_id(self) -> None:
        with self.settings:
            response = self.client.post(
                "/api/v1/auth/passkey/register/options",
                cookies={
                    "helios_session": create_session_token("TestUser")
                },
            )
        self.assertEqual(response.status_code, 200)
        options = response.json()["options"]
        self.assertEqual(options["user"]["name"], "TestUser")
        self.assertEqual(
            options["authenticatorSelection"]["userVerification"],
            "required",
        )


if __name__ == "__main__":
    unittest.main()
