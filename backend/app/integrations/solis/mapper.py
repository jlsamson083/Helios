from datetime import datetime, timezone

from app.models.energy import EnergySnapshot


def map_solis_energy(data: dict) -> EnergySnapshot:
    """
    Convert the normalized SolisService response into our
    application's EnergySnapshot model.
    """

    grid_power_kw = float(data["grid"]["power_kw"])

    # Solis grid power:
    #   positive = importing from grid
    #   negative = exporting to grid
    grid_import_kw = max(grid_power_kw, 0.0)
    grid_export_kw = max(-grid_power_kw, 0.0)

    # Solis reports the inverter timestamp as Unix epoch milliseconds.
    timestamp_ms = int(data["status"]["data_timestamp"])
    timestamp = datetime.fromtimestamp(
        timestamp_ms / 1000,
        tz=timezone.utc,
    )

    return EnergySnapshot(
        timestamp=timestamp,
        solar_power_kw=float(data["power"]["pv_power_kw"]),
        house_load_kw=float(data["power"]["home_load_kw"]),
        battery_soc_percent=float(data["battery"]["soc_percent"]),
        battery_power_kw=float(data["power"]["battery_power_kw"]),
        grid_import_kw=round(grid_import_kw, 3),
        grid_export_kw=round(grid_export_kw, 3),
    )