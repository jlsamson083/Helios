from datetime import date, datetime, timezone
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

router = APIRouter()
solis_service = SolisService()


class MeterReconciliation(BaseModel):
    current_meter_reading: float = Field(ge=0)


async def _grid_totals():
    data = await solis_service.get_inverter_status(settings.SOLIS_INVERTER_SN)
    grid = data["grid"]["energy"]
    return (
        float(grid["purchased_total_kwh"] or 0),
        float(grid["sold_total_kwh"] or 0),
    )


@router.get("/profile")
def billing_profile():
    profile = get_billing_profile()
    if profile is None:
        raise HTTPException(status_code=404, detail="No Meralco bill uploaded yet")
    return profile


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
