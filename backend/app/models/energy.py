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


class TeslaChargingDecision(BaseModel):
    available_power_kw: float
    charging_allowed: bool
    charging_current_a: float
    reason: str


class TeslaVehicleStatus(BaseModel):
    """
    Read-only Tesla vehicle status.

    This model is intentionally independent from the Tesla API.
    It can be populated with real Tesla data once the vehicle
    and API access are available.
    """

    vehicle_id: str
    battery_level_percent: float = Field(ge=0, le=100)
    charging_state: str
    charging_power_kw: float
    charging_current_a: float
    battery_range_km: float
    connected: bool


class EnergySummary(BaseModel):
    pv_surplus_before_battery_kw: float
    grid_status: str
    battery_status: str
    tesla_available_power_kw: float
    tesla_charging_allowed: bool
    tesla_charging_current_a: float
    tesla_charging_reason: str

class TeslaControllerStatus(BaseModel):
    mode: str = "simulation"
    action: str
    target_current_a: int
    reason: str
    charging: bool
    current_a: int


class HeliosEnergyStatus(BaseModel):
    snapshot: EnergySnapshot
    summary: EnergySummary
    tesla: TeslaVehicleStatus
    tesla_controller: TeslaControllerStatus