import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app
from app.services.cloud_cost import refresh_cost_status


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
            "budget_name": "Helios-Zero-Cost",
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

    def test_positive_cost_uses_one_month_scoped_alert(self) -> None:
        payload = {
            "status": "billing",
            "actual_spend": 0.01,
            "forecasted_spend": 0.01,
            "currency": "USD",
            "budget_name": "Helios-Zero-Cost",
            "checked_at": "2026-08-14T00:00:00+00:00",
            "error": None,
        }
        with (
            patch.object(settings, "OCI_COST_MONITOR_ENABLED", True),
            patch(
                "app.services.cloud_cost._read_oci_budget",
                return_value=payload,
            ),
            patch("app.services.cloud_cost._save_status"),
            patch("app.services.cloud_cost.create_alert") as create,
        ):
            asyncio.run(refresh_cost_status())
        self.assertRegex(create.call_args.kwargs["kind"], r"^cloud_cost_\d{4}-\d{2}$")
        self.assertEqual(
            create.call_args.kwargs["cooldown_minutes"], 62 * 24 * 60
        )


if __name__ == "__main__":
    unittest.main()
