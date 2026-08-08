from datetime import datetime

from pydantic import BaseModel, Field


class EnergySnapshot(BaseModel):
    timestamp: datetime
    solar_power_kw: float
    house_load_kw: float
    battery_soc_percent: float = Field(ge=0, le=100)
    battery_power_kw: float
    grid_import_kw: float
    grid_export_kw: float


class EnergySummary(BaseModel):
    solar_surplus_kw: float
    grid_status: str
    battery_status: str