from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.services.trip_scheduler import (
    TripScheduleDecision,
    TripScheduler,
)


@dataclass
class ChargingModeDecision:
    mode: str
    charging_allowed: bool
    grid_fallback_allowed: bool
    reason: str

    target_soc_percent: Optional[float] = None
    departure_time: Optional[datetime] = None

    trip_schedule: Optional[
        TripScheduleDecision
    ] = None


class ChargingModeService:
    """
    High-level Tesla charging policy for Helios.

    This layer decides WHETHER charging is allowed and
    whether grid fallback may be used.

    TeslaChargingController still decides HOW charging
    should start, stop, or vary current.

    No Tesla commands are sent here.
    """

    VALID_MODES = {
        "solar",
        "trip",
        "charge_now",
    }

    def __init__(
        self,
        trip_scheduler: Optional[
            TripScheduler
        ] = None,
    ):
        self.trip_scheduler = (
            trip_scheduler
            or TripScheduler()
        )

    def evaluate(
        self,
        *,
        mode: str,
        solar_charging_allowed: bool,

        current_tesla_soc_percent: float = 0.0,
        target_soc_percent: Optional[
            float
        ] = None,

        departure_time: Optional[
            datetime
        ] = None,

        battery_capacity_kwh: Optional[
            float
        ] = None,

        max_ac_charging_power_kw: Optional[
            float
        ] = None,

        now: Optional[
            datetime
        ] = None,
    ) -> ChargingModeDecision:

        if mode not in self.VALID_MODES:
            raise ValueError(
                f"Unsupported charging mode: {mode}"
            )

        #
        # SOLAR MODE
        #
        if mode == "solar":
            return ChargingModeDecision(
                mode="solar",
                charging_allowed=(
                    solar_charging_allowed
                ),
                grid_fallback_allowed=False,
                reason=(
                    "Solar Mode uses genuine solar "
                    "surplus only"
                    if solar_charging_allowed
                    else
                    "Solar Mode is waiting for "
                    "sufficient solar surplus"
                ),
            )

        #
        # CHARGE NOW
        #
        if mode == "charge_now":
            if (
                target_soc_percent
                is not None
                and current_tesla_soc_percent
                >= target_soc_percent
            ):
                return ChargingModeDecision(
                    mode="charge_now",
                    charging_allowed=False,
                    grid_fallback_allowed=False,
                    reason=(
                        "Tesla has already reached "
                        "the requested target SOC"
                    ),
                    target_soc_percent=(
                        target_soc_percent
                    ),
                )

            return ChargingModeDecision(
                mode="charge_now",
                charging_allowed=True,
                grid_fallback_allowed=True,
                reason=(
                    "Charge Now allows immediate "
                    "Tesla charging and permits grid "
                    "power when solar is insufficient"
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
            )

        #
        # TRIP MODE VALIDATION
        #
        if target_soc_percent is None:
            return ChargingModeDecision(
                mode="trip",
                charging_allowed=False,
                grid_fallback_allowed=False,
                reason=(
                    "Trip Mode requires a target "
                    "Tesla SOC"
                ),
                departure_time=(
                    departure_time
                ),
            )

        if departure_time is None:
            return ChargingModeDecision(
                mode="trip",
                charging_allowed=False,
                grid_fallback_allowed=False,
                reason=(
                    "Trip Mode requires a "
                    "departure time"
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
            )

        if battery_capacity_kwh is None:
            return ChargingModeDecision(
                mode="trip",
                charging_allowed=False,
                grid_fallback_allowed=False,
                reason=(
                    "Trip Mode requires Tesla "
                    "battery capacity"
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
                departure_time=(
                    departure_time
                ),
            )

        if max_ac_charging_power_kw is None:
            return ChargingModeDecision(
                mode="trip",
                charging_allowed=False,
                grid_fallback_allowed=False,
                reason=(
                    "Trip Mode requires maximum "
                    "AC charging power"
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
                departure_time=(
                    departure_time
                ),
            )

        #
        # RUN TRIP SCHEDULER
        #
        trip_schedule = (
            self.trip_scheduler.evaluate(
                current_soc_percent=(
                    current_tesla_soc_percent
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
                battery_capacity_kwh=(
                    battery_capacity_kwh
                ),
                departure_time=(
                    departure_time
                ),
                max_ac_charging_power_kw=(
                    max_ac_charging_power_kw
                ),
                now=now,
            )
        )

        #
        # Target already reached.
        #
        if trip_schedule.target_already_reached:
            return ChargingModeDecision(
                mode="trip",
                charging_allowed=False,
                grid_fallback_allowed=False,
                reason=(
                    trip_schedule.reason
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
                departure_time=(
                    departure_time
                ),
                trip_schedule=(
                    trip_schedule
                ),
            )

        #
        # Solar is available.
        #
        # Use it immediately regardless of whether
        # grid fallback is required yet.
        #
        if solar_charging_allowed:
            return ChargingModeDecision(
                mode="trip",
                charging_allowed=True,
                grid_fallback_allowed=(
                    trip_schedule
                    .grid_charging_required_now
                ),
                reason=(
                    "Trip Mode is using available "
                    "solar surplus"
                    if not trip_schedule
                    .grid_charging_required_now
                    else
                    "Trip Mode is using available "
                    "solar and grid fallback is now "
                    "permitted to protect departure"
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
                departure_time=(
                    departure_time
                ),
                trip_schedule=(
                    trip_schedule
                ),
            )

        #
        # No sufficient solar.
        #
        # If we've crossed the latest safe start,
        # grid fallback becomes mandatory.
        #
        if (
            trip_schedule
            .grid_charging_required_now
        ):
            return ChargingModeDecision(
                mode="trip",
                charging_allowed=True,
                grid_fallback_allowed=True,
                reason=(
                    "Trip Mode requires grid-assisted "
                    "charging now to meet the "
                    "departure target"
                ),
                target_soc_percent=(
                    target_soc_percent
                ),
                departure_time=(
                    departure_time
                ),
                trip_schedule=(
                    trip_schedule
                ),
            )

        #
        # Still enough time.
        #
        return ChargingModeDecision(
            mode="trip",
            charging_allowed=False,
            grid_fallback_allowed=False,
            reason=(
                "Trip Mode is waiting for solar; "
                "there is still enough time before "
                "the latest safe grid-start time"
            ),
            target_soc_percent=(
                target_soc_percent
            ),
            departure_time=(
                departure_time
            ),
            trip_schedule=(
                trip_schedule
            ),
        )