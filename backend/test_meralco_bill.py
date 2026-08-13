import unittest

from app.services.meralco_bill import parse_meralco_text


class MeralcoBillParserTests(unittest.TestCase):
    def test_parses_required_bill_values(self) -> None:
        text = """
        Billing Period 29 Jun 2026 to 28 Jul 2026
        Date of Next Meter Reading 28 Aug 2026
        Actual Consumption = 878 kWh
        Total Amount Due P 14,222.20
        Total Energy Amount 14,036.01
        Total Other Charges 186.19
        Metering Information Meter Number Previous Reading Current Reading
        Multi Registered 124BAS182274 7374 8252 1 878 kWh
        Applied Credits -643.00
        """

        result = parse_meralco_text(text)

        self.assertEqual(result["period_end"], "2026-07-28")
        self.assertEqual(result["next_meter_reading_date"], "2026-08-28")
        self.assertEqual(result["consumption_kwh"], 878.0)
        self.assertEqual(result["previous_meter_reading"], 7374.0)
        self.assertEqual(result["current_meter_reading"], 8252.0)
        self.assertEqual(result["carried_credit_php"], 643.0)
        self.assertAlmostEqual(result["import_rate_php_per_kwh"], 15.9863, places=4)


if __name__ == "__main__":
    unittest.main()
