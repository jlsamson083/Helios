from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class TripScheduleDecision:
    current_soc_percent: float
    target_soc_percent: float
    battery_capacity_kwh: float

    required_energy_kwh: float
    hours_until_departure: float

    max_ac_charging_power_kw: float
    required_charging_hours: float

    latest_grid_start_time: datetime

    grid_charging_required_now: bool
    target_already_reached: bool

    reason: str


class TripScheduler:
    """
    Determine whether Helios can continue waiting for solar
    or must start grid-assisted Tesla charging to meet a
    departure target.

    This scheduler does not send Tesla commands.
    """

    def __init__(
        self,
        *,
        charging_efficiency: float = 0.90,
        safety_buffer_minutes: int = 30,
    ):
        if not 0 < charging_efficiency <= 1:
            raise ValueError(
                "charging_efficiency must be between 0 and 1"
            )

        if safety_buffer_minutes < 0:
            raise ValueError(
                "safety_buffer_minutes cannot be negative"
            )

        self.charging_efficiency = charging_efficiency
        self.safety_buffer_minutes = (
            safety_buffer_minutes
        )

    def evaluate(
        self,
        *,
        current_soc_percent: float,
        target_soc_percent: float,
        battery_capacity_kwh: float,
        departure_time: datetime,
        max_ac_charging_power_kw: float,
        now: Optional[datetime] = None,
    ) -> TripScheduleDecision:

        current_time = (
            now
            or datetime.now().astimezone()
        )

        if battery_capacity_kwh <= 0:
            raise ValueError(
                "battery_capacity_kwh must be greater than 0"
            )

        if max_ac_charging_power_kw <= 0:
            raise ValueError(
                "max_ac_charging_power_kw must be greater than 0"
            )

        if not 0 <= current_soc_percent <= 100:
            raise ValueError(
                "current_soc_percent must be between 0 and 100"
            )

        if not 0 <= target_soc_percent <= 100:
            raise ValueError(
                "target_soc_percent must be between 0 and 100"
            )

        hours_until_departure = max(
            (
                departure_time
                - current_time
            ).total_seconds()
            / 3600.0,
            0.0,
        )

        #
        # Tesla already has enough charge.
        #
        if (
            current_soc_percent
            >= target_soc_percent
        ):
            return TripScheduleDecision(
                current_soc_percent=current_soc_percent,
                target_soc_percent=target_soc_percent,
                battery_capacity_kwh=battery_capacity_kwh,
                required_energy_kwh=0.0,
                hours_until_departure=round(
                    hours_until_departure,
                    2,
                ),
                max_ac_charging_power_kw=(
                    max_ac_charging_power_kw
                ),
                required_charging_hours=0.0,
                latest_grid_start_time=current_time,
                grid_charging_required_now=False,
                target_already_reached=True,
                reason=(
                    "Tesla has already reached the "
                    "requested Trip Mode target SOC"
                ),
            )

        #
        # Calculate how much battery SOC is missing.
        #
        soc_needed_percent = (
            target_soc_percent
            - current_soc_percent
        )

        battery_energy_needed_kwh = (
            battery_capacity_kwh
            * soc_needed_percent
            / 100.0
        )

        #
        # Account for AC charging losses.
        #
        required_energy_kwh = (
            battery_energy_needed_kwh
            / self.charging_efficiency
        )

        #
        # How long would charging take at the
        # maximum available AC charging power?
        #
        required_charging_hours = (
            required_energy_kwh
            / max_ac_charging_power_kw
        )

        #
        # Add a safety buffer so we don't plan to
        # finish exactly at departure time.
        #
        charging_duration = timedelta(
            hours=required_charging_hours
        )

        safety_buffer = timedelta(
            minutes=self.safety_buffer_minutes
        )

        latest_grid_start_time = (
            departure_time
            - charging_duration
            - safety_buffer
        )

        #
        # Once current time reaches this point,
        # waiting any longer risks missing the target.
        #
        grid_charging_required_now = (
            current_time
            >= latest_grid_start_time
        )

        if current_time >= departure_time:
            grid_charging_required_now = True

            reason = (
                "Departure time has arrived; "
                "grid charging should begin immediately"
            )

        elif grid_charging_required_now:
            reason = (
                "Helios has reached the latest safe "
                "grid-start time to meet the Trip Mode target"
            )

        else:
            reason = (
                "There is still enough time before departure; "
                "Helios can continue waiting for solar"
            )

        return TripScheduleDecision(
            current_soc_percent=current_soc_percent,
            target_soc_percent=target_soc_percent,
            battery_capacity_kwh=battery_capacity_kwh,

            required_energy_kwh=round(
                required_energy_kwh,
                2,
            ),

            hours_until_departure=round(
                hours_until_departure,
                2,
            ),

            max_ac_charging_power_kw=(
                max_ac_charging_power_kw
            ),

            required_charging_hours=round(
                required_charging_hours,
                2,
            ),

            latest_grid_start_time=(
                latest_grid_start_time
            ),

            grid_charging_required_now=(
                grid_charging_required_now
            ),

            target_already_reached=False,

            reason=reason,
        )