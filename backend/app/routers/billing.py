from datetime import date, datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.settings import settings
from app.core.database import get_connection
from app.integrations.solis.service import SolisService
from app.services.meralco_bill import (
    get_billing_profile,
    parse_meralco_pdf,
    save_billing_profile,
    save_meter_reconciliation,
)
from app.services.billing_trend import calculate_daily_grid_deltas
from app.services.meralco_email import (
    email_bill_history,
    gmail_import_status,
    sync_meralco_email_async,
)

router = APIRouter()
solis_service = SolisService()


class MeterReconciliation(BaseModel):
    current_meter_reading: float = Field(ge=0)


class SavingsBackfill(BaseModel):
    commissioned_on: date


async def _grid_totals():
    data = await solis_service.get_inverter_status(settings.SOLIS_INVERTER_SN)
    grid = data["grid"]["energy"]
    return (
        float(grid["purchased_total_kwh"] or 0),
        float(grid["sold_total_kwh"] or 0),
    )


def _cycle_data_quality(baseline_at: str, *, now: Optional[datetime] = None) -> dict:
    """Describe the measured data behind the current-cycle estimate."""
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT MAX(timestamp) AS latest_at,
                   COUNT(DISTINCT substr(timestamp, 1, 10)) AS sample_days
            FROM solis_grid_counters
            WHERE timestamp >= ?
            """,
            (baseline_at,),
        ).fetchone()
    finally:
        connection.close()

    latest_at = row["latest_at"] if row else None
    sample_days = int(row["sample_days"] or 0) if row else 0
    if latest_at is None:
        return {
            "latest_solis_at": None,
            "solis_age_minutes": None,
            "sample_days": 0,
            "data_freshness": "unavailable",
            "data_confidence": "low",
        }

    latest = datetime.fromisoformat(latest_at)
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    age_minutes = max(
        int(((now or datetime.now(timezone.utc)) - latest).total_seconds() / 60),
        0,
    )
    freshness = "fresh" if age_minutes <= 30 else "delayed" if age_minutes <= 120 else "stale"
    confidence = (
        "high"
        if freshness == "fresh" and sample_days >= 7
        else "medium"
        if freshness != "stale" and sample_days >= 3
        else "low"
    )
    return {
        "latest_solis_at": latest.isoformat(),
        "solis_age_minutes": age_minutes,
        "sample_days": sample_days,
        "data_freshness": freshness,
        "data_confidence": confidence,
    }


async def _savings_totals():
    data = await solis_service.get_inverter_status(settings.SOLIS_INVERTER_SN)
    grid = data["grid"]["energy"]
    home_load = data["energy"]["home_load"]
    return (
        float(home_load["total_kwh"] or 0),
        float(grid["purchased_total_kwh"] or 0),
        float(grid["sold_total_kwh"] or 0),
    )


async def _savings_totals_with_year():
    data = await solis_service.get_inverter_status(settings.SOLIS_INVERTER_SN)
    grid = data["grid"]["energy"]
    home_load = data["energy"]["home_load"]
    return {
        "home_total": float(home_load["total_kwh"] or 0),
        "import_total": float(grid["purchased_total_kwh"] or 0),
        "export_total": float(grid["sold_total_kwh"] or 0),
        "home_year": float(home_load["year_kwh"] or 0),
        "import_year": float(grid["purchased_year_kwh"] or 0),
        "export_year": float(grid["sold_year_kwh"] or 0),
    }


@router.get("/profile")
def billing_profile():
    profile = get_billing_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="No Meralco bill uploaded yet")
    return profile


@router.get("/email-import/status")
def email_import_status():
    return gmail_import_status()


@router.get("/email-import/history")
def email_import_history():
    return {"bills": email_bill_history()}


@router.post("/email-import/refresh")
async def refresh_email_import():
    return await sync_meralco_email_async()


@router.post("/savings/activate")
async def activate_savings():
    profile = get_billing_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Upload a Meralco bill first")
    home_load, imported, exported = await _savings_totals()
    started_at = datetime.now(timezone.utc).isoformat()
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO savings_baseline (
                id, started_at, home_load_total_kwh,
                grid_import_total_kwh, grid_export_total_kwh
            ) VALUES (1, ?, ?, ?, ?)
            """,
            (started_at, home_load, imported, exported),
        )
        connection.commit()
    finally:
        connection.close()
    return {"tracking": True, "started_at": started_at}


@router.post("/savings/backfill-solis-year")
async def backfill_savings_from_solis_year(update: SavingsBackfill):
    profile = get_billing_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Upload a Meralco bill first")
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    if update.commissioned_on.year != today.year or update.commissioned_on > today:
        raise HTTPException(
            status_code=422,
            detail="Commissioning date must be within the current year",
        )
    totals = await _savings_totals_with_year()
    started_at = datetime.combine(
        update.commissioned_on,
        datetime.min.time(),
        tzinfo=ZoneInfo("Asia/Manila"),
    ).astimezone(timezone.utc).isoformat()
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO savings_baseline (
                id, started_at, home_load_total_kwh,
                grid_import_total_kwh, grid_export_total_kwh
            ) VALUES (1, ?, ?, ?, ?)
            """,
            (
                started_at,
                max(totals["home_total"] - totals["home_year"], 0),
                max(totals["import_total"] - totals["import_year"], 0),
                max(totals["export_total"] - totals["export_year"], 0),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return {
        "tracking": True,
        "started_at": started_at,
        "source": "solis_year_counters",
    }


@router.get("/savings")
async def savings():
    profile = get_billing_profile()
    if profile is None:
        return {"tracking": False, "reason": "Upload a Meralco bill first"}
    connection = get_connection()
    try:
        baseline = connection.execute(
            "SELECT * FROM savings_baseline WHERE id = 1"
        ).fetchone()
    finally:
        connection.close()
    if baseline is None:
        return {"tracking": False, "reason": "Savings tracking is not active"}

    home_load, imported, exported = await _savings_totals()
    home_delta = max(home_load - baseline["home_load_total_kwh"], 0)
    import_delta = max(imported - baseline["grid_import_total_kwh"], 0)
    export_delta = max(exported - baseline["grid_export_total_kwh"], 0)
    import_rate = float(profile["import_rate_php_per_kwh"] or 0)
    export_rate = float(profile["export_rate_php_per_kwh"] or 0)
    without_solar = home_delta * import_rate
    measured_grid_cost = max(import_delta * import_rate - export_delta * export_rate, 0)
    savings_php = max(without_solar - measured_grid_cost, 0)
    solar_covered_kwh = max(home_delta - import_delta, 0)
    return {
        "tracking": True,
        "started_at": baseline["started_at"],
        "home_load_kwh": round(home_delta, 2),
        "grid_import_kwh": round(import_delta, 2),
        "grid_export_kwh": round(export_delta, 2),
        "without_solar_php": round(without_solar, 2),
        "measured_grid_cost_php": round(measured_grid_cost, 2),
        "savings_php": round(savings_php, 2),
        "solar_covered_percent": round(
            solar_covered_kwh / home_delta * 100 if home_delta else 0, 1
        ),
        "import_rate_php_per_kwh": import_rate,
        "export_rate_php_per_kwh": export_rate,
        "scope": "variable_energy_since_activation",
    }


@router.post("/upload")
async def upload_bill(request: Request):
    profile = parse_meralco_pdf(await request.body())
    imported, exported = await _grid_totals()
    profile.update({
        "baseline_grid_import_kwh": imported,
        "baseline_grid_export_kwh": exported,
        "baseline_at": datetime.now(timezone.utc).isoformat(),
    })
    return save_billing_profile(profile)


@router.get("/current-cycle")
async def current_cycle():
    profile = get_billing_profile()
    if profile is None or profile.get("baseline_grid_import_kwh") is None:
        raise HTTPException(status_code=404, detail="Upload a bill to start a cycle")
    imported, exported = await _grid_totals()
    period_end = date.fromisoformat(profile["period_end"])
    next_reading = date.fromisoformat(profile["next_meter_reading_date"])
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    elapsed_days = max((today - period_end).days, 1)
    cycle_days = max((next_reading - period_end).days, elapsed_days)
    estimated_import = max(imported - profile["baseline_grid_import_kwh"], 0)
    estimated_export = max(exported - profile["baseline_grid_export_kwh"], 0)
    confirmed_import = float(profile.get("confirmed_grid_import_kwh") or 0)
    confirmed_export = float(profile.get("confirmed_grid_export_kwh") or 0)
    quality = _cycle_data_quality(profile["baseline_at"])
    return {
        "grid_import_kwh": confirmed_import + estimated_import,
        "grid_export_kwh": confirmed_export + estimated_export,
        "confirmed_grid_import_kwh": confirmed_import,
        "estimated_grid_import_kwh": estimated_import,
        "confirmed_grid_export_kwh": confirmed_export,
        "estimated_grid_export_kwh": estimated_export,
        "baseline_at": profile["baseline_at"],
        "elapsed_days": elapsed_days,
        "cycle_days": cycle_days,
        "calculation_basis": "uploaded_bill_plus_solis",
        **quality,
    }


@router.get("/daily-grid")
def daily_grid_trend():
    profile = get_billing_profile()
    if profile is None or profile.get("baseline_at") is None:
        raise HTTPException(status_code=404, detail="Upload a bill to start a cycle")
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT timestamp, grid_import_total_kwh, grid_export_total_kwh
            FROM solis_grid_counters WHERE timestamp >= ?
            ORDER BY timestamp ASC
            """,
            (profile["baseline_at"],),
        ).fetchall()
    finally:
        connection.close()
    days = calculate_daily_grid_deltas(
        rows,
        baseline_import_kwh=float(profile["baseline_grid_import_kwh"]),
        baseline_export_kwh=float(profile["baseline_grid_export_kwh"]),
    )
    measured_import = sum(day["import_kwh"] for day in days)
    measured_export = sum(day["export_kwh"] for day in days)
    completed_days = max(len(days), 1)
    average_import = measured_import / completed_days
    average_export = measured_export / completed_days
    period_end = date.fromisoformat(profile["period_end"])
    next_reading = date.fromisoformat(profile["next_meter_reading_date"])
    today = datetime.now(ZoneInfo("Asia/Manila")).date()
    elapsed_days = max((today - period_end).days, 1)
    cycle_days = max((next_reading - period_end).days, elapsed_days)
    remaining_days = max(cycle_days - elapsed_days, 0)
    confirmed_import = float(profile.get("confirmed_grid_import_kwh") or 0)
    confirmed_export = float(profile.get("confirmed_grid_export_kwh") or 0)
    confidence = "high" if len(days) >= 7 else "medium" if len(days) >= 3 else "low"
    return {
        "days": days[-31:],
        "sample_days": len(days),
        "confidence": confidence,
        "average_daily_import_kwh": round(average_import, 2),
        "average_daily_export_kwh": round(average_export, 2),
        "projected_cycle_import_kwh": round(
            confirmed_import + measured_import + average_import * remaining_days, 1
        ),
        "projected_cycle_export_kwh": round(
            confirmed_export + measured_export + average_export * remaining_days, 1
        ),
    }


@router.put("/meter-reconciliation")
async def reconcile_meter(update: MeterReconciliation):
    profile = get_billing_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="Upload a bill first")
    if update.current_meter_reading < profile["current_meter_reading"]:
        raise HTTPException(
            status_code=422,
            detail="Current reading cannot be lower than the uploaded bill closing reading",
        )
    imported, exported = await _grid_totals()
    saved = save_meter_reconciliation(
        current_meter_reading=update.current_meter_reading,
        confirmed_grid_import_kwh=(
            update.current_meter_reading - profile["current_meter_reading"]
        ),
        baseline_grid_import_kwh=imported,
        baseline_grid_export_kwh=exported,
    )
    return {
        "confirmed_grid_import_kwh": saved["confirmed_grid_import_kwh"],
        "confirmed_meter_reading": saved["confirmed_meter_reading"],
        "confirmed_at": saved["confirmed_at"],
    }
