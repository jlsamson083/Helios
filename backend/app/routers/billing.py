from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.settings import settings
from app.integrations.solis.service import SolisService
from app.services.meralco_bill import (
    get_billing_profile,
    parse_meralco_pdf,
    save_billing_profile,
    save_meter_reconciliation,
)

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
