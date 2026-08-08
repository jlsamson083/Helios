from fastapi import APIRouter

from app.models.energy import EnergySnapshot
from app.services.energy import build_energy_summary

router = APIRouter()


@router.post("/snapshot")
def create_energy_snapshot(snapshot: EnergySnapshot):
    summary = build_energy_summary(snapshot)

    return {
        "snapshot": snapshot,
        "summary": summary
    }