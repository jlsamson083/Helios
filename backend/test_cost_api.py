import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app


class CostApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)
        cls.headers = {"X-Helios-Key": "test-secret"}

    def auth_enabled(self):
        return patch.multiple(
            settings,
            API_AUTH_REQUIRED=True,
            HELIOS_API_KEY="test-secret",
        )

    def test_cost_status_requires_authentication(self) -> None:
        with self.auth_enabled():
            response = self.client.get("/api/v1/cost/status")
        self.assertEqual(response.status_code, 401)

    def test_cost_status_returns_verified_or_unconnected_state(self) -> None:
        payload = {
            "status": "zero_cost",
            "actual_spend": 0.0,
            "forecasted_spend": 0.0,
            "currency": "USD",
            "budget_name": "Helios Zero Cost",
            "checked_at": "2026-08-14T00:00:00+00:00",
            "error": None,
        }
        with (
            self.auth_enabled(),
            patch("app.routers.cost.get_cost_status", return_value=payload),
        ):
            response = self.client.get(
                "/api/v1/cost/status", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_manual_refresh_uses_oci_monitor(self) -> None:
        payload = {"status": "billing", "actual_spend": 0.01}
        with (
            self.auth_enabled(),
            patch(
                "app.routers.cost.refresh_cost_status",
                new=AsyncMock(return_value=payload),
            ),
        ):
            response = self.client.post(
                "/api/v1/cost/refresh", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)


if __name__ == "__main__":
    unittest.main()
