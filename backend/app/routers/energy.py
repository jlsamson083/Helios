from fastapi import APIRouter

from app.models.energy import EnergySnapshot
from app.services.energy import calculate_solar_surplus

router = APIRouter()


@router.post("/snapshot")
def create_energy_snapshot(snapshot: EnergySnapshot):
    solar_surplus_kw = calculate_solar_surplus(snapshot)

    return {
        "snapshot": snapshot,
        "solar_surplus_kw": solar_surplus_kw
    }