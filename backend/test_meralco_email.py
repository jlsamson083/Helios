import unittest
from email.message import EmailMessage
from unittest.mock import patch

from app.services.meralco_email import _update_profile_from_pdfs, parse_meralco_email


class MeralcoEmailTests(unittest.TestCase):
    def test_parses_official_bill_summary(self) -> None:
        message = EmailMessage()
        message["From"] = "MANILA ELECTRIC COMPANY <customercare@meralco.com.ph>"
        message["Subject"] = "Meralco Bill for July 2026"
        message["Message-ID"] = "<bill-july@example>"
        message["Date"] = "Thu, 30 Jul 2026 11:12:00 +0800"
        message.set_content(
            """
            Billing Period: 29 June 2026 to 28 July 2026
            kWh Consumption: 878
            Current Amount Due: PHP 12,345.67
            Due Date: 10 August 2026
            """
        )

        result = parse_meralco_email(message)

        self.assertIsNotNone(result)
        self.assertEqual(result["period_end"], "2026-07-28")
        self.assertEqual(result["consumption_kwh"], 878.0)
        self.assertEqual(result["amount_due_php"], 12345.67)
        self.assertEqual(result["due_date"], "2026-08-10")

    def test_ignores_non_meralco_sender(self) -> None:
        message = EmailMessage()
        message["From"] = "attacker@example.com"
        message["Subject"] = "Meralco Bill for July 2026"
        message.set_content("Billing Period: 29 June 2026 to 28 July 2026")

        self.assertIsNone(parse_meralco_email(message))

    def test_ignores_receipts_and_payment_confirmations(self) -> None:
        message = EmailMessage()
        message["From"] = "customercare@meralco.com.ph"
        message["Subject"] = "Payment Confirmation"
        message.set_content("Current Amount Due: PHP 0.00")

        self.assertIsNone(parse_meralco_email(message))

    def test_new_pdf_profile_uses_period_end_solis_baseline(self) -> None:
        profile = {"period_end": "2026-08-28", "billing_period": "29 Jul 2026 to 28 Aug 2026"}
        baseline = {
            "baseline_grid_import_kwh": 88.2,
            "baseline_grid_export_kwh": 14.4,
            "baseline_at": "2026-08-28T16:00:00+00:00",
        }
        with (
            patch("app.services.meralco_email.get_billing_profile", return_value={"period_end": "2026-07-28"}),
            patch("app.services.meralco_email._solis_baseline_for_bill", return_value=baseline),
            patch("app.services.meralco_email.save_billing_profile") as save,
        ):
            updated = _update_profile_from_pdfs([profile])

        self.assertTrue(updated)
        save.assert_called_once_with({**profile, **baseline})

    def test_existing_or_older_pdf_does_not_reset_profile(self) -> None:
        with (
            patch("app.services.meralco_email.get_billing_profile", return_value={"period_end": "2026-08-28"}),
            patch("app.services.meralco_email.save_billing_profile") as save,
        ):
            updated = _update_profile_from_pdfs([{"period_end": "2026-08-28"}])

        self.assertFalse(updated)
        save.assert_not_called()


if __name__ == "__main__":
    unittest.main()
