from datetime import datetime, timedelta, timezone

from app.services.charging_mode import (
    ChargingModeService,
)


PH_TIMEZONE = timezone(
    timedelta(hours=8)
)


def print_decision(
    name: str,
    decision,
):
    print()
    print(name)
    print("-" * len(name))

    print(
        "Mode:",
        decision.mode,
    )

    print(
        "Charging allowed:",
        decision.charging_allowed,
    )

    print(
        "Grid fallback:",
        decision.grid_fallback_allowed,
    )

    print(
        "Reason:",
        decision.reason,
    )

    if decision.trip_schedule:
        schedule = decision.trip_schedule

        print(
            "Required energy:",
            schedule.required_energy_kwh,
            "kWh",
        )

        print(
            "Latest grid start:",
            schedule.latest_grid_start_time,
        )

        print(
            "Grid required now:",
            schedule.grid_charging_required_now,
        )


def run_tests():
    service = ChargingModeService()

    departure = datetime(
        2026,
        8,
        14,
        7,
        0,
        tzinfo=PH_TIMEZONE,
    )

    #
    # 1. Normal solar mode.
    #
    decision = service.evaluate(
        mode="solar",
        solar_charging_allowed=True,
    )

    print_decision(
        "1. Solar Mode with surplus",
        decision,
    )

    #
    # 2. Rainy evening.
    #
    # Trip Mode should wait because there
    # is still plenty of time.
    #
    decision = service.evaluate(
        mode="trip",
        solar_charging_allowed=False,
        current_tesla_soc_percent=35,
        target_soc_percent=80,
        departure_time=departure,
        battery_capacity_kwh=75,
        max_ac_charging_power_kw=7.36,
        now=datetime(
            2026,
            8,
            13,
            20,
            0,
            tzinfo=PH_TIMEZONE,
        ),
    )

    print_decision(
        "2. Rainy evening - Trip Mode",
        decision,
    )

    #
    # 3. Rainy late night.
    #
    # Latest grid start has passed.
    #
    decision = service.evaluate(
        mode="trip",
        solar_charging_allowed=False,
        current_tesla_soc_percent=35,
        target_soc_percent=80,
        departure_time=departure,
        battery_capacity_kwh=75,
        max_ac_charging_power_kw=7.36,
        now=datetime(
            2026,
            8,
            14,
            2,
            30,
            tzinfo=PH_TIMEZONE,
        ),
    )

    print_decision(
        "3. Rainy late night - Trip Mode",
        decision,
    )

    #
    # 4. Solar available during Trip Mode.
    #
    decision = service.evaluate(
        mode="trip",
        solar_charging_allowed=True,
        current_tesla_soc_percent=50,
        target_soc_percent=80,
        departure_time=departure,
        battery_capacity_kwh=75,
        max_ac_charging_power_kw=7.36,
        now=datetime(
            2026,
            8,
            13,
            16,
            0,
            tzinfo=PH_TIMEZONE,
        ),
    )

    print_decision(
        "4. Trip Mode using solar",
        decision,
    )

    #
    # 5. Charge Now.
    #
    decision = service.evaluate(
        mode="charge_now",
        solar_charging_allowed=False,
        current_tesla_soc_percent=30,
        target_soc_percent=80,
    )

    print_decision(
        "5. Charge Now",
        decision,
    )

    #
    # 6. Target already reached.
    #
    decision = service.evaluate(
        mode="trip",
        solar_charging_allowed=False,
        current_tesla_soc_percent=85,
        target_soc_percent=80,
        departure_time=departure,
        battery_capacity_kwh=75,
        max_ac_charging_power_kw=7.36,
        now=datetime(
            2026,
            8,
            13,
            23,
            0,
            tzinfo=PH_TIMEZONE,
        ),
    )

    print_decision(
        "6. Trip target reached",
        decision,
    )


if __name__ == "__main__":
    run_tests()