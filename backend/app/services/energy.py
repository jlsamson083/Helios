from app.models.energy import EnergySnapshot


def calculate_solar_surplus(snapshot: EnergySnapshot) -> float:
    return round(
        max(snapshot.solar_power_kw - snapshot.house_load_kw, 0),
        2
    )