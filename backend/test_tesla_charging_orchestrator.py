from datetime import datetime, timedelta, timezone

from app.services.tesla_charging_orchestrator import (
    TeslaChargingOrchestrator,
)


PH_TIMEZONE = timezone(
    timedelta(hours=8)
)


def print_result(
    name: str,
    result,
):
    print()
    print(name)
    print("-" * len(name))

    print(
        "Mode:",
        result.mode_decision.mode,
    )

    print(
        "Charging allowed:",
        result.mode_decision.charging_allowed,
    )

    print(
        "Grid fallback:",
        result.grid_fallback_active,
    )

    print(
        "Solar available:",
        result.available_power_kw,
        "kW",
    )

    print(
        "Effective budget:",
        result.effective_power_budget_kw,
        "kW",
    )

    print(
        "Controller action:",
        result.controller_command.action,
    )

    print(
        "Target current:",
        result.controller_command.target_current_a,
        "A",
    )

    print(
        "Mode reason:",
        result.mode_decision.reason,
    )

    print(
        "Controller reason:",
        result.controller_command.reason,
    )


def run_tests():
    departure = datetime(
        2026,
        8,
        14,
        7,
        0,
        tzinfo=PH_TIMEZONE,
    )

    #
    # 1. Solar Mode with enough solar.
    #
    orchestrator = TeslaChargingOrchestrator()

    for time_s in [0, 15, 30, 45]:
        result = orchestrator.evaluate(
            mode="solar",
            solar_charging_allowed=True,
            solar_available_power_kw=4.8,
            current_tesla_soc_percent=40,
            max_ac_charging_power_kw=7.36,
            now_datetime=datetime(
                2026,
                8,
                13,
                14,
                0,
                tzinfo=PH_TIMEZONE,
            ),
            now_monotonic=float(time_s),
            snapshot_age_seconds=20,
        )

    print_result(
        "1. Solar Mode",
        result,
    )

    #
    # 2. Rainy evening Trip Mode.
    #
    orchestrator = TeslaChargingOrchestrator()

    result = orchestrator.evaluate(
        mode="trip",
        solar_charging_allowed=False,
        solar_available_power_kw=0.3,
        current_tesla_soc_percent=35,
        target_soc_percent=80,
        departure_time=departure,
        battery_capacity_kwh=75,
        max_ac_charging_power_kw=7.36,
        now_datetime=datetime(
            2026,
            8,
            13,
            20,
            0,
            tzinfo=PH_TIMEZONE,
        ),
        now_monotonic=0.0,
        snapshot_age_seconds=20,
    )

    print_result(
        "2. Rainy evening Trip Mode",
        result,
    )

    #
    # 3. Late-night Trip Mode.
    # Grid fallback must be active.
    #
    orchestrator = TeslaChargingOrchestrator()

    for time_s in [0, 15, 30, 45]:
        result = orchestrator.evaluate(
            mode="trip",
            solar_charging_allowed=False,
            solar_available_power_kw=0.0,
            current_tesla_soc_percent=35,
            target_soc_percent=80,
            departure_time=departure,
            battery_capacity_kwh=75,
            max_ac_charging_power_kw=7.36,
            now_datetime=datetime(
                2026,
                8,
                14,
                2,
                30,
                tzinfo=PH_TIMEZONE,
            ),
            now_monotonic=float(time_s),
            snapshot_age_seconds=20,
        )

    print_result(
        "3. Late-night Trip Mode",
        result,
    )

    #
    # 4. Charge Now at night.
    #
    orchestrator = TeslaChargingOrchestrator()

    for time_s in [0, 15, 30, 45]:
        result = orchestrator.evaluate(
            mode="charge_now",
            solar_charging_allowed=False,
            solar_available_power_kw=0.0,
            current_tesla_soc_percent=30,
            target_soc_percent=80,
            max_ac_charging_power_kw=7.36,
            now_datetime=datetime(
                2026,
                8,
                13,
                23,
                0,
                tzinfo=PH_TIMEZONE,
            ),
            now_monotonic=float(time_s),
            snapshot_age_seconds=20,
        )

    print_result(
        "4. Charge Now at night",
        result,
    )

    #
    # 5. Stale telemetry.
    #
    orchestrator = TeslaChargingOrchestrator()

    for time_s in [0, 15, 30, 45]:
        result = orchestrator.evaluate(
            mode="charge_now",
            solar_charging_allowed=False,
            solar_available_power_kw=0.0,
            current_tesla_soc_percent=30,
            target_soc_percent=80,
            max_ac_charging_power_kw=7.36,
            now_datetime=datetime(
                2026,
                8,
                13,
                23,
                0,
                tzinfo=PH_TIMEZONE,
            ),
            now_monotonic=float(time_s),
            snapshot_age_seconds=500,
        )

    print_result(
        "5. Stale telemetry safety",
        result,
    )


if __name__ == "__main__":
    run_tests()