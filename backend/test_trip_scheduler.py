from datetime import datetime, timedelta, timezone

from app.services.trip_scheduler import TripScheduler


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
        f"Current SOC:              "
        f"{decision.current_soc_percent:.1f}%"
    )

    print(
        f"Target SOC:               "
        f"{decision.target_soc_percent:.1f}%"
    )

    print(
        f"Battery capacity:         "
        f"{decision.battery_capacity_kwh:.1f} kWh"
    )

    print(
        f"Required AC energy:       "
        f"{decision.required_energy_kwh:.2f} kWh"
    )

    print(
        f"Hours until departure:    "
        f"{decision.hours_until_departure:.2f} h"
    )

    print(
        f"Required charging time:   "
        f"{decision.required_charging_hours:.2f} h"
    )

    print(
        f"Latest grid start:        "
        f"{decision.latest_grid_start_time}"
    )

    print(
        f"Grid required now:        "
        f"{decision.grid_charging_required_now}"
    )

    print(
        f"Target already reached:   "
        f"{decision.target_already_reached}"
    )

    print(
        f"Reason:                   "
        f"{decision.reason}"
    )


def run_tests():
    scheduler = TripScheduler(
        charging_efficiency=0.90,
        safety_buffer_minutes=30,
    )

    #
    # Scenario 1:
    #
    # Evening before a trip.
    # There is plenty of time left, so Helios
    # should be allowed to wait for solar.
    #
    now = datetime(
        2026,
        8,
        13,
        20,
        0,
        tzinfo=PH_TIMEZONE,
    )

    departure = datetime(
        2026,
        8,
        14,
        7,
        0,
        tzinfo=PH_TIMEZONE,
    )

    decision = scheduler.evaluate(
        current_soc_percent=35,
        target_soc_percent=80,
        battery_capacity_kwh=75,
        departure_time=departure,
        max_ac_charging_power_kw=7.36,
        now=now,
    )

    print_decision(
        "1. Evening before trip",
        decision,
    )

    #
    # Scenario 2:
    #
    # Same trip, but it is now much later.
    # Helios may have reached the latest safe
    # grid-start time.
    #
    now = datetime(
        2026,
        8,
        14,
        2,
        30,
        tzinfo=PH_TIMEZONE,
    )

    decision = scheduler.evaluate(
        current_soc_percent=35,
        target_soc_percent=80,
        battery_capacity_kwh=75,
        departure_time=departure,
        max_ac_charging_power_kw=7.36,
        now=now,
    )

    print_decision(
        "2. Late night before trip",
        decision,
    )

    #
    # Scenario 3:
    #
    # Tesla already reached the target.
    #
    now = datetime(
        2026,
        8,
        14,
        5,
        0,
        tzinfo=PH_TIMEZONE,
    )

    decision = scheduler.evaluate(
        current_soc_percent=82,
        target_soc_percent=80,
        battery_capacity_kwh=75,
        departure_time=departure,
        max_ac_charging_power_kw=7.36,
        now=now,
    )

    print_decision(
        "3. Target already reached",
        decision,
    )

    #
    # Scenario 4:
    #
    # Departure has already arrived but
    # Tesla is still below target.
    #
    now = datetime(
        2026,
        8,
        14,
        7,
        5,
        tzinfo=PH_TIMEZONE,
    )

    decision = scheduler.evaluate(
        current_soc_percent=60,
        target_soc_percent=80,
        battery_capacity_kwh=75,
        departure_time=departure,
        max_ac_charging_power_kw=7.36,
        now=now,
    )

    print_decision(
        "4. Departure deadline reached",
        decision,
    )


if __name__ == "__main__":
    run_tests()