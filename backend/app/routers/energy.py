import time
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.settings import settings
from app.integrations.solis.service import SolisService
from app.models.energy import (
    EnergySnapshot,
    HeliosEnergyStatus,
    TeslaControllerStatus,
    TeslaVehicleStatus,
)
from app.services.charging_settings import (
    charging_settings,
    save_charging_settings,
)
from app.services.energy import build_energy_summary
from app.services.history import (
    get_energy_snapshots,
    save_energy_snapshot,
)
from app.services.tesla_charging_orchestrator import (
    TeslaChargingOrchestrator,
)


router = APIRouter()

solis_service = SolisService()

#
# Keep this at module level so controller state,
# hysteresis and stability timers persist.
#
tesla_charging_orchestrator = (
    TeslaChargingOrchestrator()
)

#
# 230V x 32A ≈ 7.36 kW
#
TESLA_MAX_AC_POWER_KW = 7.36


class ChargingSettingsUpdate(BaseModel):
    mode: Literal[
        "solar",
        "trip",
        "charge_now",
    ]

    simulated_tesla_soc_percent: float = Field(
        default=40.0,
        ge=0.0,
        le=100.0,
    )

    target_soc_percent: Optional[float] = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
    )

    departure_time: Optional[datetime] = None


@router.post("/snapshot")
def create_energy_snapshot(
    snapshot: EnergySnapshot,
):
    summary = build_energy_summary(
        snapshot
    )

    return {
        "snapshot": snapshot,
        "summary": summary,
    }


@router.get("/solis")
async def get_solis_energy():
    """
    Return current Solis energy information.

    READ-ONLY.
    """

    snapshot = (
        await solis_service.get_energy_snapshot(
            settings.SOLIS_INVERTER_SN
        )
    )

    save_energy_snapshot(
        snapshot
    )

    summary = build_energy_summary(
        snapshot
    )

    return {
        "snapshot": snapshot,
        "summary": summary,
    }


@router.get("/tesla")
def get_tesla_status():
    """
    Return simulated Tesla status until the real
    Tesla integration is connected.
    """

    return TeslaVehicleStatus(
        vehicle_id="future-tesla",
        battery_level_percent=(
            charging_settings
            .simulated_tesla_soc_percent
        ),
        charging_state="Not Available",
        charging_power_kw=0.0,
        charging_current_a=0.0,
        battery_range_km=0.0,
        connected=False,
    )


@router.get("/charging-mode")
def get_charging_mode():
    """
    Return the current Helios Tesla charging policy.

    This remains simulation-only.
    """

    return {
        "mode": charging_settings.mode,
        "simulated_tesla_soc_percent": (
            charging_settings
            .simulated_tesla_soc_percent
        ),
        "target_soc_percent": (
            charging_settings.target_soc_percent
        ),
        "departure_time": (
            charging_settings.departure_time
        ),
        "battery_capacity_kwh": (
            charging_settings
            .battery_capacity_kwh
        ),
        "max_ac_charging_power_kw": (
            TESLA_MAX_AC_POWER_KW
        ),
        "simulation": True,
    }


@router.put("/charging-mode")
def update_charging_mode(
    request: ChargingSettingsUpdate,
):
    """
    Change the simulated Helios charging mode.

    Modes:
    - solar
    - trip
    - charge_now

    No command is sent to Tesla.
    """

    if (
        request.mode == "trip"
        and request.departure_time is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Trip Mode requires a departure time"
            ),
        )

    if (
        request.mode == "trip"
        and request.target_soc_percent is None
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Trip Mode requires a target SOC"
            ),
        )

    if (
        request.target_soc_percent is not None
        and request.target_soc_percent
        < request.simulated_tesla_soc_percent
        and request.mode == "trip"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Trip Mode target SOC cannot be lower "
                "than the current simulated Tesla SOC"
            ),
        )

    charging_settings.mode = (
        request.mode
    )

    charging_settings.simulated_tesla_soc_percent = (
        request.simulated_tesla_soc_percent
    )

    charging_settings.target_soc_percent = (
        request.target_soc_percent
    )

    charging_settings.departure_time = (
        request.departure_time
    )
    save_charging_settings(
    charging_settings
    )

    #
    # Reset pending controller state whenever the
    # user changes charging policy.
    #
    # This prevents a stability timer from the previous
    # mode carrying into the new mode.
    #
    tesla_charging_orchestrator.controller.state.charging = (
        False
    )

    tesla_charging_orchestrator.controller.state.current_a = (
        0
    )

    tesla_charging_orchestrator.controller.state.pending_current_a = (
        None
    )

    tesla_charging_orchestrator.controller.state.pending_since = (
        None
    )

    return get_charging_mode()


@router.get(
    "/status",
    response_model=HeliosEnergyStatus,
)
async def get_energy_status():
    """
    Return complete live Helios energy status.

    Tesla control remains SIMULATION ONLY.
    No Tesla command is sent.
    """

    #
    # 1. Solis telemetry
    #
    snapshot = (
        await solis_service.get_energy_snapshot(
            settings.SOLIS_INVERTER_SN
        )
    )

    save_energy_snapshot(
        snapshot
    )

    #
    # 2. Energy decision engine
    #
    summary = build_energy_summary(
        snapshot
    )

    #
    # 3. Determine telemetry age
    #
    current_datetime = datetime.now(
        snapshot.timestamp.tzinfo
    )

    snapshot_age_seconds = max(
        (
            current_datetime
            - snapshot.timestamp
        ).total_seconds(),
        0.0,
    )

    #
    # 4. Simulated Tesla
    #
    tesla = TeslaVehicleStatus(
        vehicle_id="future-tesla",
        battery_level_percent=(
            charging_settings
            .simulated_tesla_soc_percent
        ),
        charging_state="Not Available",
        charging_power_kw=0.0,
        charging_current_a=0.0,
        battery_range_km=0.0,
        connected=False,
    )

    #
    # 5. Full Tesla charging orchestration
    #
    orchestrator_result = (
        tesla_charging_orchestrator.evaluate(
            mode=(
                charging_settings.mode
            ),

            solar_charging_allowed=(
                summary.tesla_charging_allowed
            ),

            solar_available_power_kw=(
                summary.tesla_available_power_kw
            ),

            current_tesla_soc_percent=(
                charging_settings
                .simulated_tesla_soc_percent
            ),

            target_soc_percent=(
                charging_settings
                .target_soc_percent
            ),

            departure_time=(
                charging_settings
                .departure_time
            ),

            battery_capacity_kwh=(
                charging_settings
                .battery_capacity_kwh
            ),

            max_ac_charging_power_kw=(
                TESLA_MAX_AC_POWER_KW
            ),

            now_datetime=(
                current_datetime
            ),

            now_monotonic=(
                time.monotonic()
            ),

            snapshot_age_seconds=(
                snapshot_age_seconds
            ),
        )
    )

    controller_command = (
        orchestrator_result.controller_command
    )

    #
    # 6. Controller simulation status
    #
    tesla_controller = TeslaControllerStatus(
        mode="simulation",
        action=(
            controller_command.action
        ),
        target_current_a=(
            controller_command
            .target_current_a
        ),
        reason=(
            controller_command.reason
        ),
        charging=(
            tesla_charging_orchestrator
            .controller
            .state
            .charging
        ),
        current_a=(
            tesla_charging_orchestrator
            .controller
            .state
            .current_a
        ),
    )

    return {
        "snapshot": snapshot,
        "summary": summary,
        "tesla": tesla,
        "tesla_controller": (
            tesla_controller
        ),
    }


@router.get("/history/summary")
async def get_energy_history_summary():
    """
    Return Solis cumulative energy counters.

    READ-ONLY.
    """

    data = (
        await solis_service.get_inverter_status(
            settings.SOLIS_INVERTER_SN
        )
    )

    energy = data["energy"]
    battery = data["battery"]
    grid = data["grid"]["energy"]

    return {
        "today": {
            "solar_generation_kwh": (
                energy[
                    "solar_generation"
                ]["today_kwh"]
                or 0.0
            ),
            "home_load_kwh": (
                energy[
                    "home_load"
                ]["today_kwh"]
                or 0.0
            ),
            "battery_charge_kwh": (
                battery[
                    "charge_energy"
                ]["today_kwh"]
                or 0.0
            ),
            "battery_discharge_kwh": (
                battery[
                    "discharge_energy"
                ]["today_kwh"]
                or 0.0
            ),
            "grid_import_kwh": (
                grid[
                    "purchased_today_kwh"
                ]
                or 0.0
            ),
            "grid_export_kwh": (
                grid[
                    "sold_today_kwh"
                ]
                or 0.0
            ),
        },

        "month": {
            "solar_generation_kwh": (
                energy[
                    "solar_generation"
                ]["month_kwh"]
                or 0.0
            ),
            "home_load_kwh": (
                energy[
                    "home_load"
                ]["month_kwh"]
                or 0.0
            ),
            "battery_charge_kwh": (
                battery[
                    "charge_energy"
                ]["month_kwh"]
                or 0.0
            ),
            "battery_discharge_kwh": (
                battery[
                    "discharge_energy"
                ]["month_kwh"]
                or 0.0
            ),
            "grid_import_kwh": (
                grid[
                    "purchased_month_kwh"
                ]
                or 0.0
            ),
            "grid_export_kwh": (
                grid[
                    "sold_month_kwh"
                ]
                or 0.0
            ),
        },

        "year": {
            "solar_generation_kwh": (
                energy[
                    "solar_generation"
                ]["year_kwh"]
                or 0.0
            ),
            "home_load_kwh": (
                energy[
                    "home_load"
                ]["year_kwh"]
                or 0.0
            ),
            "battery_charge_kwh": (
                battery[
                    "charge_energy"
                ]["year_kwh"]
                or 0.0
            ),
            "battery_discharge_kwh": (
                battery[
                    "discharge_energy"
                ]["year_kwh"]
                or 0.0
            ),
            "grid_import_kwh": (
                grid[
                    "purchased_year_kwh"
                ]
                or 0.0
            ),
            "grid_export_kwh": (
                grid[
                    "sold_year_kwh"
                ]
                or 0.0
            ),
        },
    }


@router.get("/history/timeseries")
def get_energy_history_timeseries(
    limit: int = 500,
):
    return {
        "items": get_energy_snapshots(
            limit
        )
    }
