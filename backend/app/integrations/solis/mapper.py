from app.models.energy import EnergySnapshot


def map_solis_energy(data: dict) -> EnergySnapshot:
    return EnergySnapshot(
        timestamp=data["timestamp"],
        solar_power_kw=data["solar_power_kw"],
        house_load_kw=data["house_load_kw"],
        battery_soc_percent=data["battery_soc_percent"],
        battery_power_kw=data["battery_power_kw"],
        grid_import_kw=data["grid_import_kw"],
        grid_export_kw=data["grid_export_kw"],
    )