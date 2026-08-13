from app.models.energy import (
    EnergySnapshot,
    EnergySummary,
    TeslaChargingDecision,
)
from app.core.settings import settings


MIN_TESLA_CHARGING_CURRENT = 6.0

BATTERY_CRITICAL_SOC = 30.0
BATTERY_TESLA_READY_SOC = 50.0
BATTERY_HIGH_SOC = 80.0


def calculate_solar_surplus(
    snapshot: EnergySnapshot,
) -> float:
    """
    Calculate PV power remaining after the house load.

    This represents the raw solar surplus before considering
    battery charging.
    """

    return round(
        max(
            snapshot.solar_power_kw
            - snapshot.house_load_kw,
            0,
        ),
        2,
    )


def calculate_grid_status(
    snapshot: EnergySnapshot,
) -> str:
    GRID_DEADBAND_KW = 0.05

    importing = (
        snapshot.grid_import_kw
        > GRID_DEADBAND_KW
    )

    exporting = (
        snapshot.grid_export_kw
        > GRID_DEADBAND_KW
    )

    if importing and exporting:
        return "conflict"

    if importing:
        return "importing"

    if exporting:
        return "exporting"

    return "balanced"


def calculate_battery_status(
    snapshot: EnergySnapshot,
) -> str:
    if snapshot.battery_power_kw > 0:
        return "charging"

    if snapshot.battery_power_kw < 0:
        return "discharging"

    return "idle"


def calculate_tesla_available_power(
    snapshot: EnergySnapshot,
) -> float:
    """
    Calculate the solar power that Tesla can use without
    consuming power that is currently charging the battery.

    PV surplus:
        PV - house load

    If the battery is charging:
        Tesla available = PV surplus - battery charging power

    If the battery is idle:
        Tesla gets the full PV surplus.

    If the battery is discharging:
        Tesla still gets the PV surplus. We never add the
        battery discharge to Tesla's available solar power.
    """

    solar_surplus = calculate_solar_surplus(snapshot)

    if snapshot.battery_power_kw > 0:
        solar_surplus -= snapshot.battery_power_kw

    return round(
        max(solar_surplus, 0),
        2,
    )


def calculate_tesla_charging_decision(
    snapshot: EnergySnapshot,
) -> TeslaChargingDecision:
    """
    Determine whether Tesla charging is allowed and,
    if allowed, calculate the recommended charging current.

    This function is READ-ONLY. It does not send any command
    to Tesla or the inverter.
    """

    available_power_kw = calculate_tesla_available_power(
        snapshot
    )
    # Safety rule:
    # Never allow Tesla charging while the house battery
    # is actively discharging.
    if snapshot.battery_power_kw < 0:
        return TeslaChargingDecision(
            available_power_kw=available_power_kw,
            charging_allowed=False,
            charging_current_a=0.0,
            reason=(
                "House battery is discharging; "
                "Tesla charging is blocked"
            ),
        )
    if available_power_kw <= 0:
        return TeslaChargingDecision(
            available_power_kw=0.0,
            charging_allowed=False,
            charging_current_a=0.0,
            reason="No solar surplus available",
        )

    if snapshot.battery_soc_percent < BATTERY_CRITICAL_SOC:
            return TeslaChargingDecision(
            available_power_kw=available_power_kw,
            charging_allowed=False,
            charging_current_a=0.0,
            reason=(
                f"Battery SOC {snapshot.battery_soc_percent:.1f}% "
                f"is below the critical reserve of "
                f"{BATTERY_CRITICAL_SOC:.1f}%"
            ),
        )

    if snapshot.battery_soc_percent < BATTERY_TESLA_READY_SOC:
        return TeslaChargingDecision(
            available_power_kw=available_power_kw,
            charging_allowed=False,
            charging_current_a=0.0,
            reason=(
                f"Battery SOC {snapshot.battery_soc_percent:.1f}% "
                f"is below the Tesla charging threshold of "
                f"{BATTERY_TESLA_READY_SOC:.1f}%; "
                f"prioritizing house battery charging"
            ),
        )

    available_current = (
        available_power_kw * 1000
    ) / settings.TESLA_CHARGER_VOLTAGE

    charging_current = round(
        min(
            available_current,
            settings.TESLA_MAX_CURRENT,
        ),
        1,
    )

    if (
        charging_current
        < MIN_TESLA_CHARGING_CURRENT
    ):
        return TeslaChargingDecision(
            available_power_kw=available_power_kw,
            charging_allowed=False,
            charging_current_a=0.0,
            reason=(
                f"Available solar power only supports "
                f"{charging_current:.1f}A, below the minimum "
                f"Tesla charging current of "
                f"{MIN_TESLA_CHARGING_CURRENT:.1f}A"
            ),
        )

    return TeslaChargingDecision(
        available_power_kw=available_power_kw,
        charging_allowed=True,
        charging_current_a=charging_current,
        reason=(
            "Solar surplus available for Tesla charging"
        ),
    )


def calculate_tesla_charging_allowed(
    snapshot: EnergySnapshot,
) -> bool:
    return calculate_tesla_charging_decision(
        snapshot
    ).charging_allowed


def calculate_tesla_charging_current(
    snapshot: EnergySnapshot,
) -> float:
    return calculate_tesla_charging_decision(
        snapshot
    ).charging_current_a


def build_energy_summary(
    snapshot: EnergySnapshot,
) -> EnergySummary:
    pv_surplus_before_battery_kw = calculate_solar_surplus(
        snapshot
    )

    grid_status = calculate_grid_status(
        snapshot
    )

    battery_status = calculate_battery_status(
        snapshot
    )

    tesla_decision = calculate_tesla_charging_decision(
        snapshot
    )

    return EnergySummary(
        pv_surplus_before_battery_kw=(
        pv_surplus_before_battery_kw
        ),
        grid_status=grid_status,
        battery_status=battery_status,
        tesla_available_power_kw=(
            tesla_decision.available_power_kw
        ),
        tesla_charging_allowed=(
            tesla_decision.charging_allowed
        ),
        tesla_charging_current_a=(
            tesla_decision.charging_current_a
        ),
        tesla_charging_reason=(
            tesla_decision.reason
        ),
    )
