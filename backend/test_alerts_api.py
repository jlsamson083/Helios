import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app


class AlertsApiTests(unittest.TestCase):
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

    def test_alerts_require_authentication(self) -> None:
        with self.auth_enabled():
            response = self.client.get("/api/v1/alerts")
        self.assertEqual(response.status_code, 401)

    def test_alert_list_returns_unread_count(self) -> None:
        payload = {
            "items": [{"id": 1, "title": "Grid import detected"}],
            "unread_count": 1,
        }
        with (
            self.auth_enabled(),
            patch("app.routers.alerts.list_alerts", return_value=payload),
        ):
            response = self.client.get(
                "/api/v1/alerts", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), payload)

    def test_mark_missing_alert_returns_not_found(self) -> None:
        with (
            self.auth_enabled(),
            patch("app.routers.alerts.mark_alert_read", return_value=None),
        ):
            response = self.client.put(
                "/api/v1/alerts/999/read", headers=self.headers
            )
        self.assertEqual(response.status_code, 404)

    def test_mark_all_uses_static_route(self) -> None:
        with (
            self.auth_enabled(),
            patch("app.routers.alerts.mark_all_alerts_read", return_value=3),
        ):
            response = self.client.put(
                "/api/v1/alerts/read-all", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"updated": 3})

    def test_notification_requires_authentication(self) -> None:
        with self.auth_enabled():
            response = self.client.post("/api/v1/alerts/test-notification")
        self.assertEqual(response.status_code, 401)

    def test_notification_reports_delivery_count(self) -> None:
        result = {"sent": 1, "failed": 0, "removed": 0}
        with (
            self.auth_enabled(),
            patch("app.routers.alerts.send_push_alert", return_value=result),
        ):
            response = self.client.post(
                "/api/v1/alerts/test-notification", headers=self.headers
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), result)


if __name__ == "__main__":
    unittest.main()
