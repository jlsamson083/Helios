import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app


class ApiAuthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(app)

    def auth_enabled(self):
        return patch.multiple(
            settings,
            API_AUTH_REQUIRED=True,
            HELIOS_API_KEY="test-secret",
        )

    def test_health_remains_public(self) -> None:
        with self.auth_enabled():
            response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)

    def test_energy_endpoint_rejects_missing_key(self) -> None:
        with self.auth_enabled():
            response = self.client.get("/api/v1/energy/charging-mode")

        self.assertEqual(response.status_code, 401)

    def test_root_rejects_missing_key(self) -> None:
        with self.auth_enabled():
            response = self.client.get("/")

        self.assertEqual(response.status_code, 401)

    def test_energy_endpoint_accepts_valid_key(self) -> None:
        with self.auth_enabled():
            response = self.client.get(
                "/api/v1/energy/charging-mode",
                headers={"X-Helios-Key": "test-secret"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["simulation"])


if __name__ == "__main__":
    unittest.main()
