import io
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from pypdf import PdfReader

from app.core.database import get_connection


def _number(pattern: str, text: str, label: str) -> float:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError(f"Could not find {label} in this Meralco bill")
    return float(match.group(1).replace(",", ""))


def parse_meralco_text(text: str) -> dict:
    normalized = " ".join(text.replace("₱", "P").split())
    period = re.search(
        r"Billing Period\s+(\d{1,2} \w{3} \d{4})\s+to\s+(\d{1,2} \w{3} \d{4})",
        normalized,
        re.IGNORECASE,
    )
    if not period:
        raise ValueError("Could not find the billing period")

    period_end = datetime.strptime(period.group(2), "%d %b %Y").date()
    next_reading_match = re.search(
        r"Date of Next Meter Reading\s+(\d{1,2} \w{3} \d{4})",
        normalized,
        re.IGNORECASE,
    )
    if not next_reading_match:
        raise ValueError("Could not find the next meter reading date")
    next_reading = datetime.strptime(
        next_reading_match.group(1), "%d %b %Y"
    ).date()
    consumption = _number(
        r"Actual Consumption.*?([\d,]+)\s*kWh",
        normalized,
        "actual consumption",
    )
    total = _number(
        r"Total Amount Due\s+[^0-9]*([\d,]+\.\d{2})",
        normalized,
        "total amount due",
    )
    energy_amount = _number(
        r"Total Energy Amount\s+([\d,]+\.\d{2})",
        normalized,
        "total energy amount",
    )
    other_charges = _number(
        r"Total Other Charges\s+([\d,]+\.\d{2})",
        normalized,
        "total other charges",
    )
    meter = re.search(
        r"Meter Number\s+Previous Reading\s+Current Reading\s+Multi Registered\s+\w+\s+(\d+)\s+(\d+)\s+1\s+[\d,]+\s*kWh",
        normalized,
        re.IGNORECASE,
    )
    if not meter:
        raise ValueError("Could not find previous and current meter readings")

    export_rate_match = re.search(
        r"rate this month\s*-?\s*Export\s+P?\s*-?\s*([\d.]+)\s*per kWh",
        normalized,
        re.IGNORECASE,
    )
    applied_credit_match = re.search(
        r"Applied Credits\s+-?\s*([\d,]+\.\d{2})",
        normalized,
        re.IGNORECASE,
    )

    return {
        "billing_period": f"{period.group(1)} to {period.group(2)}",
        "period_end": period_end.isoformat(),
        "next_meter_reading_date": next_reading.isoformat(),
        "consumption_kwh": consumption,
        "energy_amount_php": energy_amount,
        "other_charges_php": other_charges,
        "total_amount_php": total,
        "previous_meter_reading": float(meter.group(1)),
        "current_meter_reading": float(meter.group(2)),
        "import_rate_php_per_kwh": energy_amount / consumption,
        "export_rate_php_per_kwh": (
            float(export_rate_match.group(1)) if export_rate_match else None
        ),
        "carried_credit_php": (
            float(applied_credit_match.group(1).replace(",", ""))
            if applied_credit_match
            else 0.0
        ),
    }


def parse_meralco_pdf(content: bytes) -> dict:
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="PDF must be 10 MB or smaller")
    if not content.startswith(b"%PDF"):
        raise HTTPException(status_code=415, detail="Only PDF bills are supported")
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return parse_meralco_text(text)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def save_billing_profile(profile: dict) -> dict:
    saved = {**profile, "updated_at": datetime.now(timezone.utc).isoformat()}
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO billing_profile (
                id, billing_period, period_end, consumption_kwh,
                energy_amount_php, other_charges_php, total_amount_php,
                previous_meter_reading, current_meter_reading,
                import_rate_php_per_kwh, export_rate_php_per_kwh, updated_at,
                baseline_grid_import_kwh, baseline_grid_export_kwh, baseline_at,
                confirmed_grid_import_kwh, confirmed_grid_export_kwh,
                confirmed_meter_reading, confirmed_at
                , next_meter_reading_date, carried_credit_php
            ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                billing_period=excluded.billing_period,
                period_end=excluded.period_end,
                consumption_kwh=excluded.consumption_kwh,
                energy_amount_php=excluded.energy_amount_php,
                other_charges_php=excluded.other_charges_php,
                total_amount_php=excluded.total_amount_php,
                previous_meter_reading=excluded.previous_meter_reading,
                current_meter_reading=excluded.current_meter_reading,
                import_rate_php_per_kwh=excluded.import_rate_php_per_kwh,
                export_rate_php_per_kwh=excluded.export_rate_php_per_kwh,
                updated_at=excluded.updated_at,
                baseline_grid_import_kwh=excluded.baseline_grid_import_kwh,
                baseline_grid_export_kwh=excluded.baseline_grid_export_kwh,
                baseline_at=excluded.baseline_at,
                confirmed_grid_import_kwh=NULL,
                confirmed_grid_export_kwh=NULL,
                confirmed_meter_reading=NULL,
                confirmed_at=NULL,
                next_meter_reading_date=excluded.next_meter_reading_date,
                carried_credit_php=excluded.carried_credit_php
            """,
            (
                saved["billing_period"], saved["period_end"],
                saved["consumption_kwh"], saved["energy_amount_php"],
                saved["other_charges_php"], saved["total_amount_php"],
                saved["previous_meter_reading"], saved["current_meter_reading"],
                saved["import_rate_php_per_kwh"], saved["export_rate_php_per_kwh"],
                saved["updated_at"],
                saved.get("baseline_grid_import_kwh"),
                saved.get("baseline_grid_export_kwh"),
                saved.get("baseline_at"),
                None, None, None, None,
                saved["next_meter_reading_date"],
                saved["carried_credit_php"],
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return saved


def get_billing_profile() -> Optional[dict]:
    connection = get_connection()
    try:
        row = connection.execute("SELECT * FROM billing_profile WHERE id = 1").fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def save_meter_reconciliation(
    *,
    current_meter_reading: float,
    confirmed_grid_import_kwh: float,
    baseline_grid_import_kwh: float,
    baseline_grid_export_kwh: float,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE billing_profile SET
                confirmed_meter_reading = ?,
                confirmed_grid_import_kwh = ?,
                confirmed_grid_export_kwh = 0,
                confirmed_at = ?,
                baseline_grid_import_kwh = ?,
                baseline_grid_export_kwh = ?,
                baseline_at = ?
            WHERE id = 1
            """,
            (
                current_meter_reading,
                confirmed_grid_import_kwh,
                now,
                baseline_grid_import_kwh,
                baseline_grid_export_kwh,
                now,
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return get_billing_profile() or {}
