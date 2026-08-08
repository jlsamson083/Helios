from app.models.energy import EnergySnapshot, EnergySummary


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


def build_energy_summary(snapshot: EnergySnapshot) -> EnergySummary:
    solar_surplus_kw = calculate_solar_surplus(snapshot)
    grid_status = calculate_grid_status(snapshot)

    return EnergySummary(
        solar_surplus_kw=solar_surplus_kw,
        grid_status=grid_status
    )