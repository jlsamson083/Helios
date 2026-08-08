from app.models.energy import EnergySnapshot, EnergySummary
from app.core.settings import settings


def calculate_solar_surplus(snapshot: EnergySnapshot) -> float:
    return round(
        max(snapshot.solar_power_kw - snapshot.house_load_kw, 0),
        2
    )


def calculate_grid_status(snapshot: EnergySnapshot) -> str:
    if snapshot.grid_import_kw > 0 and snapshot.grid_export_kw > 0:
        return "conflict"

    if snapshot.grid_import_kw > 0:
        return "importing"

    if snapshot.grid_export_kw > 0:
        return "exporting"

    return "balanced"


def calculate_battery_status(snapshot: EnergySnapshot) -> str:
    if snapshot.battery_power_kw > 0:
        return "charging"

    if snapshot.battery_power_kw < 0:
        return "discharging"

    return "idle"

def calculate_tesla_available_power(snapshot: EnergySnapshot) -> float:
    return round(
        max(snapshot.solar_power_kw - snapshot.house_load_kw, 0),
        2
    )

def calculate_tesla_charging_allowed(snapshot: EnergySnapshot) -> bool:
    return (
        calculate_tesla_available_power(snapshot) > 0
        and snapshot.battery_soc_percent >= settings.MIN_BATTERY_SOC
    )

def calculate_tesla_charging_current(snapshot: EnergySnapshot) -> float:
    if not calculate_tesla_charging_allowed(snapshot):
        return 0.0

    available_power_kw = calculate_tesla_available_power(snapshot)

    available_current = (
        available_power_kw * 1000
    ) / settings.TESLA_CHARGER_VOLTAGE

    return round(
        min(available_current, settings.TESLA_MAX_CURRENT),
        1
    )

def build_energy_summary(snapshot: EnergySnapshot) -> EnergySummary:
    solar_surplus_kw = calculate_solar_surplus(snapshot)
    grid_status = calculate_grid_status(snapshot)
    battery_status = calculate_battery_status(snapshot)
    tesla_available_power_kw = calculate_tesla_available_power(snapshot)
    tesla_charging_allowed = calculate_tesla_charging_allowed(snapshot)
    tesla_charging_current_a = calculate_tesla_charging_current(snapshot)


    return EnergySummary(
    solar_surplus_kw=solar_surplus_kw,
    grid_status=grid_status,
    battery_status=battery_status,
    tesla_available_power_kw=tesla_available_power_kw,
    tesla_charging_allowed=tesla_charging_allowed,
    tesla_charging_current_a=tesla_charging_current_a
)

