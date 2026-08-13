from app.services.tesla_charging_controller import (
    TeslaChargingController,
)


def print_step(
    time_s: int,
    available_kw: float,
    allowed: bool,
    command,
):
    print(
        f"{time_s:>4}s | "
        f"{available_kw:>4.1f} kW | "
        f"Allowed={str(allowed):<5} | "
        f"{command.action.upper():<11} | "
        f"{command.target_current_a:>2} A | "
        f"{command.reason}"
    )


def run_scenario():
    controller = TeslaChargingController()

    scenario = [
        # time, Tesla-available power, charging allowed

        (0,   4.8, True),
        (15,  4.9, True),
        (30,  5.0, True),
        (45,  4.9, True),

        # Stable long enough to start.
        (60,  4.9, True),

        # Small fluctuations should be ignored.
        (75,  4.7, True),
        (90,  4.9, True),

        # Solar drops because of clouds.
        (105, 3.4, True),
        (115, 3.4, True),

        # Solar recovers briefly.
        (130, 4.7, True),
        (145, 4.7, True),

        # Still waiting because increases are slower.
        (160, 4.7, True),
        (175, 4.7, True),

        # Enough stability to increase.
        (190, 4.7, True),

        # Heavy cloud / house load spike.
        (205, 1.3, True),

        # Below charging minimum — stop immediately.
        (220, 1.0, True),

        # Solar returns.
        (235, 5.5, True),
        (250, 5.5, True),
        (265, 5.5, True),
        (280, 5.5, True),

        # Stable again.
        (295, 5.5, True),

        # House battery starts discharging.
        # Energy decision engine blocks Tesla regardless
        # of available-power calculation.
        (310, 5.5, False),
    ]

    print()
    print(
        "TIME | POWER  | ALLOWED       | ACTION      "
        "| AMP | REASON"
    )
    print("-" * 120)

    for time_s, available_kw, allowed in scenario:
        command = controller.update(
            available_power_kw=available_kw,
            charging_allowed=allowed,
            now=float(time_s),
        )

        print_step(
            time_s,
            available_kw,
            allowed,
            command,
        )
def run_oscillation_scenario():
    controller = TeslaChargingController()

    scenario = [
        # Establish stable charging.
        (0, 4.8, True),
        (15, 4.9, True),
        (30, 4.8, True),
        (45, 4.9, True),

        # Clouds / sun oscillating around ~19-20A.
        (60, 4.7, True),
        (75, 4.9, True),
        (90, 4.7, True),
        (105, 4.9, True),
        (120, 4.8, True),

        # More noticeable solar drop.
        (135, 3.8, True),
        (140, 4.0, True),
        (145, 3.8, True),
        (150, 3.8, True),

        # Recovery.
        (165, 4.8, True),
        (180, 4.9, True),
        (195, 4.8, True),
        (210, 4.9, True),
    ]

    print()
    print()
    print("=== CLOUD OSCILLATION TEST ===")
    print(
        "TIME | POWER  | ALLOWED       | ACTION      "
        "| AMP | REASON"
    )
    print("-" * 120)

    for time_s, available_kw, allowed in scenario:
        command = controller.update(
            available_power_kw=available_kw,
            charging_allowed=allowed,
            now=float(time_s),
        )

        print_step(
            time_s,
            available_kw,
            allowed,
            command,
        )

def run_stale_data_scenario():
    controller = TeslaChargingController()

    print()
    print()
    print("=== STALE SOLIS DATA TEST ===")
    print(
        "TIME | AGE    | POWER  | ACTION      "
        "| AMP | REASON"
    )
    print("-" * 110)

    scenario = [
        # time, age, available power, allowed
        (0,   10,  4.8, True),
        (15,  20,  4.8, True),
        (30,  30,  4.8, True),
        (45,  40,  4.8, True),

        # Controller should now be charging.
        (60,  60,  4.8, True),

        # Solis data becomes too old.
        (75,  480, 4.8, True),

        # Still stale.
        (90,  600, 4.8, True),

        # Fresh telemetry returns.
        (105, 5,   4.8, True),
        (120, 10,  4.8, True),
        (135, 15,  4.8, True),
        (150, 20,  4.8, True),
    ]

    for time_s, age_s, available_kw, allowed in scenario:
        command = controller.update(
            available_power_kw=available_kw,
            charging_allowed=allowed,
            now=float(time_s),
            snapshot_age_seconds=float(age_s),
        )

        print(
            f"{time_s:>4}s | "
            f"{age_s:>4}s | "
            f"{available_kw:>4.1f} kW | "
            f"{command.action.upper():<11} | "
            f"{command.target_current_a:>2} A | "
            f"{command.reason}"
        )


if __name__ == "__main__":
    run_scenario()
    run_oscillation_scenario()
    run_stale_data_scenario()
