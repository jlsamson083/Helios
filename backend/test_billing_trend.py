import unittest

from app.services.billing_trend import calculate_daily_grid_deltas


class BillingTrendTests(unittest.TestCase):
    def test_daily_deltas_use_lifetime_counter_differences(self) -> None:
        rows = [
            {"timestamp": "2026-08-14T00:00:00+00:00", "grid_import_total_kwh": 101.0, "grid_export_total_kwh": 50.5},
            {"timestamp": "2026-08-14T08:00:00+00:00", "grid_import_total_kwh": 102.5, "grid_export_total_kwh": 52.0},
            {"timestamp": "2026-08-15T00:00:00+00:00", "grid_import_total_kwh": 103.0, "grid_export_total_kwh": 53.0},
        ]
        result = calculate_daily_grid_deltas(
            rows, baseline_import_kwh=100.0, baseline_export_kwh=50.0
        )
        self.assertEqual(result[0]["date"], "2026-08-14")
        self.assertEqual(result[0]["import_kwh"], 2.5)
        self.assertEqual(result[0]["export_kwh"], 2.0)
        self.assertEqual(result[1]["import_kwh"], 0.5)
        self.assertEqual(result[1]["export_kwh"], 1.0)

    def test_counter_reset_never_creates_negative_energy(self) -> None:
        rows = [
            {"timestamp": "2026-08-14T00:00:00+00:00", "grid_import_total_kwh": 5.0, "grid_export_total_kwh": 3.0},
        ]
        result = calculate_daily_grid_deltas(
            rows, baseline_import_kwh=100.0, baseline_export_kwh=50.0
        )
        self.assertEqual(result[0]["import_kwh"], 0)
        self.assertEqual(result[0]["export_kwh"], 0)


if __name__ == "__main__":
    unittest.main()
