from datetime import datetime, timezone, timedelta

from app.models.energy import EnergySnapshot
from app.services.energy import (
    calculate_tesla_charging_decision,
    build_energy_summary,
)


PH_TIMEZONE = timezone(timedelta(hours=8))


def make_snapshot(
    solar_power_kw: float,
    house_load_kw: float,
    battery_soc_percent: float,
    battery_power_kw: float = 0.0,
    grid_import_kw: float = 0.0,
    grid_export_kw: float = 0.0,
) -> EnergySnapshot:
    return EnergySnapshot(
        timestamp=datetime.now(PH_TIMEZONE),
        solar_power_kw=solar_power_kw,
        house_load_kw=house_load_kw,
        battery_soc_percent=battery_soc_percent,
        battery_power_kw=battery_power_kw,
        grid_import_kw=grid_import_kw,
        grid_export_kw=grid_export_kw,
    )


def test_no_solar():
    snapshot = make_snapshot(
        solar_power_kw=0.0,
        house_load_kw=2.5,
        battery_soc_percent=80.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.charging_allowed is False
    assert decision.charging_current_a == 0.0
    assert decision.available_power_kw == 0.0


def test_battery_critical_soc():
    snapshot = make_snapshot(
        solar_power_kw=8.0,
        house_load_kw=1.0,
        battery_soc_percent=20.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.charging_allowed is False
    assert decision.charging_current_a == 0.0
    assert "critical reserve" in decision.reason


def test_battery_below_tesla_ready_soc():
    snapshot = make_snapshot(
        solar_power_kw=8.0,
        house_load_kw=1.0,
        battery_soc_percent=40.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.charging_allowed is False
    assert decision.charging_current_a == 0.0
    assert "prioritizing house battery" in decision.reason


def test_battery_ready_with_surplus():
    snapshot = make_snapshot(
        solar_power_kw=6.0,
        house_load_kw=1.0,
        battery_soc_percent=80.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.charging_allowed is True
    assert decision.available_power_kw == 5.0
    assert decision.charging_current_a == 20.8


def test_battery_discharging_blocks_tesla():
    snapshot = make_snapshot(
        solar_power_kw=8.0,
        house_load_kw=1.0,
        battery_soc_percent=80.0,
        battery_power_kw=-2.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.charging_allowed is False
    assert decision.charging_current_a == 0.0
    assert "battery is discharging" in decision.reason.lower()


def test_battery_charging_is_subtracted():
    snapshot = make_snapshot(
        solar_power_kw=8.0,
        house_load_kw=1.0,
        battery_soc_percent=80.0,
        battery_power_kw=6.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.available_power_kw == 1.0
    assert decision.charging_allowed is False
    assert decision.charging_current_a == 0.0


def test_battery_charging_lightly_leaves_surplus():
    snapshot = make_snapshot(
        solar_power_kw=8.0,
        house_load_kw=1.0,
        battery_soc_percent=80.0,
        battery_power_kw=1.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.available_power_kw == 6.0
    assert decision.charging_allowed is True
    assert decision.charging_current_a == 25.0


def test_below_minimum_tesla_current():
    snapshot = make_snapshot(
        solar_power_kw=2.0,
        house_load_kw=1.0,
        battery_soc_percent=80.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.available_power_kw == 1.0
    assert decision.charging_allowed is False
    assert decision.charging_current_a == 0.0
    assert "below the minimum" in decision.reason


def test_house_load_exceeds_solar():
    snapshot = make_snapshot(
        solar_power_kw=1.0,
        house_load_kw=2.0,
        battery_soc_percent=80.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.available_power_kw == 0.0
    assert decision.charging_allowed is False


def test_tesla_current_is_capped_at_32a():
    snapshot = make_snapshot(
        solar_power_kw=12.0,
        house_load_kw=1.0,
        battery_soc_percent=95.0,
    )

    decision = calculate_tesla_charging_decision(snapshot)

    assert decision.charging_allowed is True
    assert decision.charging_current_a == 32.0


def test_energy_summary():
    snapshot = make_snapshot(
        solar_power_kw=6.0,
        house_load_kw=1.0,
        battery_soc_percent=80.0,
    )

    summary = build_energy_summary(snapshot)

    assert summary.pv_surplus_before_battery_kw == 5.0
    assert summary.battery_status == "idle"
    assert summary.grid_status == "balanced"
    assert summary.tesla_charging_allowed is True
    assert summary.tesla_charging_current_a == 20.8


def run_all_tests():
    tests = [
        test_no_solar,
        test_battery_critical_soc,
        test_battery_below_tesla_ready_soc,
        test_battery_ready_with_surplus,
        test_battery_discharging_blocks_tesla,
        test_battery_charging_is_subtracted,
        test_battery_charging_lightly_leaves_surplus,
        test_below_minimum_tesla_current,
        test_house_load_exceeds_solar,
        test_tesla_current_is_capped_at_32a,
        test_energy_summary,
    ]

    for test in tests:
        test()
        print(f"PASS: {test.__name__}")

    print()
    print(f"All {len(tests)} Helios energy tests passed.")

def test_battery_positive_power_is_charging():
    snapshot = make_snapshot(
        solar_power_kw=1.491,
        house_load_kw=0.490,
        battery_soc_percent=38.0,
    )
    snapshot.battery_power_kw = 0.738

    summary = build_energy_summary(snapshot)

    assert summary.battery_status == "charging"


def test_battery_negative_power_is_discharging():
    snapshot = make_snapshot(
        solar_power_kw=0.300,
        house_load_kw=0.650,
        battery_soc_percent=38.0,
    )
    snapshot.battery_power_kw = -0.558

    summary = build_energy_summary(snapshot)

    assert summary.battery_status == "discharging"
    assert summary.tesla_charging_allowed is False

test_battery_positive_power_is_charging()
print("PASS: test_battery_positive_power_is_charging")

test_battery_negative_power_is_discharging()
print("PASS: test_battery_negative_power_is_discharging")

if __name__ == "__main__":
    run_all_tests()
