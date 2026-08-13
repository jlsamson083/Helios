from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.services.charging_mode import (
    ChargingModeDecision,
    ChargingModeService,
)
from app.services.tesla_charging_controller import (
    TeslaChargingCommand,
    TeslaChargingController,
)


@dataclass
class TeslaChargingOrchestratorResult:
    mode_decision: ChargingModeDecision
    controller_command: TeslaChargingCommand

    available_power_kw: float
    effective_power_budget_kw: float

    grid_fallback_active: bool


class TeslaChargingOrchestrator:
    """
    Combines:

    - ChargingModeService
    - TripScheduler
    - TeslaChargingController

    into one final simulated Tesla charging decision.

    No Tesla command is sent from this service.
    """

    def __init__(
        self,
        *,
        mode_service: Optional[
            ChargingModeService
        ] = None,
        controller: Optional[
            TeslaChargingController
        ] = None,
    ):
        self.mode_service = (
            mode_service
            or ChargingModeService()
        )

        self.controller = (
            controller
            or TeslaChargingController()
        )

    def evaluate(
        self,
        *,
        mode: str,

        solar_charging_allowed: bool,
        solar_available_power_kw: float,

        current_tesla_soc_percent: float = 0.0,
        target_soc_percent: Optional[float] = None,
        departure_time: Optional[datetime] = None,

        battery_capacity_kwh: Optional[float] = None,
        max_ac_charging_power_kw: float = 7.36,

        now_datetime: Optional[datetime] = None,
        now_monotonic: float,

        snapshot_age_seconds: float = 0.0,
    ) -> TeslaChargingOrchestratorResult:

        mode_decision = self.mode_service.evaluate(
            mode=mode,
            solar_charging_allowed=(
                solar_charging_allowed
            ),
            current_tesla_soc_percent=(
                current_tesla_soc_percent
            ),
            target_soc_percent=(
                target_soc_percent
            ),
            departure_time=(
                departure_time
            ),
            battery_capacity_kwh=(
                battery_capacity_kwh
            ),
            max_ac_charging_power_kw=(
                max_ac_charging_power_kw
            ),
            now=now_datetime,
        )

        #
        # Decide how much power the controller
        # is allowed to use.
        #
        if not mode_decision.charging_allowed:
            effective_power_budget_kw = 0.0

        elif mode_decision.grid_fallback_allowed:
            effective_power_budget_kw = (
                max_ac_charging_power_kw
            )

        else:
            effective_power_budget_kw = max(
                solar_available_power_kw,
                0.0,
            )

        controller_command = (
            self.controller.update(
                available_power_kw=(
                    effective_power_budget_kw
                ),
                charging_allowed=(
                    mode_decision.charging_allowed
                ),
                now=now_monotonic,
                snapshot_age_seconds=(
                    snapshot_age_seconds
                ),
            )
        )

        return TeslaChargingOrchestratorResult(
            mode_decision=mode_decision,
            controller_command=controller_command,
            available_power_kw=(
                solar_available_power_kw
            ),
            effective_power_budget_kw=(
                effective_power_budget_kw
            ),
            grid_fallback_active=(
                mode_decision.grid_fallback_allowed
            ),
        )