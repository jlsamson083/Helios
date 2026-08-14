import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app


class BillingApiTests(unittest.TestCase):
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

    def test_upload_requires_authentication(self) -> None:
        with self.auth_enabled():
            response = self.client.post(
                "/api/v1/billing/upload",
                content=b"not-a-pdf",
                headers={"Content-Type": "application/pdf"},
            )

        self.assertEqual(response.status_code, 401)

    def test_upload_rejects_non_pdf_content(self) -> None:
        with self.auth_enabled():
            response = self.client.post(
                "/api/v1/billing/upload",
                content=b"not-a-pdf",
                headers={
                    **self.headers,
                    "Content-Type": "application/pdf",
                },
            )

        self.assertEqual(response.status_code, 415)

    def test_current_cycle_combines_confirmed_and_solis_delta(self) -> None:
        profile = {
            "period_end": "2026-07-28",
            "next_meter_reading_date": "2026-08-28",
            "baseline_grid_import_kwh": 900.0,
            "baseline_grid_export_kwh": 450.0,
            "baseline_at": "2026-08-13T10:00:00+00:00",
            "confirmed_grid_import_kwh": 98.0,
            "confirmed_grid_export_kwh": 0.0,
        }

        with (
            self.auth_enabled(),
            patch(
                "app.routers.billing.get_billing_profile",
                return_value=profile,
            ),
            patch(
                "app.routers.billing._grid_totals",
                new=AsyncMock(return_value=(902.5, 451.25)),
            ),
        ):
            response = self.client.get(
                "/api/v1/billing/current-cycle",
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["confirmed_grid_import_kwh"], 98.0)
        self.assertEqual(data["estimated_grid_import_kwh"], 2.5)
        self.assertEqual(data["grid_import_kwh"], 100.5)
        self.assertEqual(data["estimated_grid_export_kwh"], 1.25)
        self.assertEqual(data["grid_export_kwh"], 1.25)

    def test_meter_reconciliation_rejects_reading_before_bill(self) -> None:
        profile = {"current_meter_reading": 8252.0}

        with (
            self.auth_enabled(),
            patch(
                "app.routers.billing.get_billing_profile",
                return_value=profile,
            ),
        ):
            response = self.client.put(
                "/api/v1/billing/meter-reconciliation",
                json={"current_meter_reading": 8200},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 422)

    def test_meter_reconciliation_saves_exact_delta(self) -> None:
        profile = {"current_meter_reading": 8252.0}
        saved = {
            "confirmed_grid_import_kwh": 98.0,
            "confirmed_meter_reading": 8350.0,
            "confirmed_at": "2026-08-13T10:00:00+00:00",
        }

        with (
            self.auth_enabled(),
            patch(
                "app.routers.billing.get_billing_profile",
                return_value=profile,
            ),
            patch(
                "app.routers.billing._grid_totals",
                new=AsyncMock(return_value=(1000.0, 500.0)),
            ),
            patch(
                "app.routers.billing.save_meter_reconciliation",
                return_value=saved,
            ) as save,
        ):
            response = self.client.put(
                "/api/v1/billing/meter-reconciliation",
                json={"current_meter_reading": 8350},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["confirmed_grid_import_kwh"], 98.0)
        self.assertEqual(
            save.call_args.kwargs["confirmed_grid_import_kwh"],
            98.0,
        )

    def test_savings_waits_for_activation_baseline(self) -> None:
        connection = MagicMock()
        connection.execute.return_value.fetchone.return_value = None
        with (
            self.auth_enabled(),
            patch("app.routers.billing.get_billing_profile", return_value={"import_rate_php_per_kwh": 15}),
            patch("app.routers.billing.get_connection", return_value=connection),
        ):
            response = self.client.get(
                "/api/v1/billing/savings", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["tracking"])

    def test_activate_savings_uses_live_solis_totals(self) -> None:
        connection = MagicMock()
        with (
            self.auth_enabled(),
            patch("app.routers.billing.get_billing_profile", return_value={"import_rate_php_per_kwh": 15}),
            patch(
                "app.routers.billing._savings_totals",
                new=AsyncMock(return_value=(1200.0, 900.0, 300.0)),
            ),
            patch("app.routers.billing.get_connection", return_value=connection),
        ):
            response = self.client.post(
                "/api/v1/billing/savings/activate", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["tracking"])
        connection.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
