from app.models.energy import EnergySnapshot, EnergySummary


def calculate_solar_surplus(snapshot: EnergySnapshot) -> float:
    return round(
        max(snapshot.solar_power_kw - snapshot.house_load_kw, 0),
        2
    )


def build_energy_summary(snapshot: EnergySnapshot) -> EnergySummary:
    solar_surplus_kw = calculate_solar_surplus(snapshot)

    return EnergySummary(
        solar_surplus_kw=solar_surplus_kw
    )