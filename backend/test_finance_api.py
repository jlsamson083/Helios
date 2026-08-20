import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.auth import create_session_token
from app.core.settings import settings
from app.main import app


class FinanceApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.settings = patch.multiple(
            settings,
            API_AUTH_REQUIRED=True,
            HELIOS_API_KEY="api-secret",
            HELIOS_SESSION_SECRET="session-secret",
            HELIOS_OWNER_USERNAME="Eros",
        )

    def test_owner_can_view_finance_summary(self) -> None:
        with self.settings:
            token = create_session_token("Eros")
            response = self.client.get(
                "/api/v1/finance/summary",
                cookies={"helios_session": token},
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn("months", response.json())

    def test_member_cannot_view_finance_summary(self) -> None:
        with self.settings:
            token = create_session_token("Winter")
            response = self.client.get(
                "/api/v1/finance/summary",
                cookies={"helios_session": token},
            )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
