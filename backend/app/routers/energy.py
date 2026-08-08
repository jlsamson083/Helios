from fastapi import APIRouter

from app.models.energy import EnergySnapshot

router = APIRouter()


@router.post("/snapshot")
def create_energy_snapshot(snapshot: EnergySnapshot):
    return snapshot