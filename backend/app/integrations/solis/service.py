from datetime import datetime
from typing import Any, Dict, Optional

from app.integrations.solis.client import SolisClient
from app.models.energy import EnergySnapshot


def power_value(value: Any) -> float:
    """
    Safely convert a Solis numeric value to float.
    """
    if value is None:
        return 0.0

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def parse_timestamp(value: Any) -> datetime:
    """
    Convert Solis local timestamp string into datetime.

    Expected:
    2026-08-09 11:16:16 (UTC+08:00)

    Falls back to local system time if parsing fails.
    """
    if isinstance(value, datetime):
        return value

    if isinstance(value, str):
        try:
            return datetime.strptime(
                value,
                "%Y-%m-%d %H:%M:%S (UTC%z)",
            )
        except ValueError:
            pass

    return datetime.now().astimezone()


class SolisService:
    """
    Business/data-normalization layer for Solis Cloud.

    SolisClient handles communication with Solis Cloud.
    SolisService converts the large Solis response into
    a smaller, predictable structure for Helios.
    """

    def __init__(self, client: Optional[SolisClient] = None):
        self.client = client or SolisClient()

    async def get_inverter_status(
        self,
        inverter_sn: str,
    ) -> Dict[str, Any]:
        response = await self.client.get_inverter_detail(
            inverter_sn
        )

        if not response:
            raise RuntimeError(
                "Solis returned an empty response"
            )

        if response.get("success") is not True:
            raise RuntimeError(
                f"Solis API request failed: {response}"
            )

        data = response.get("data")

        if not isinstance(data, dict):
            raise RuntimeError(
                "Solis API response does not contain valid inverter data"
            )

        return {
        "inverter": self._inverter_details(data),
        "power": self._power_details(data),
        "battery": self._battery_details(data),
        "grid": self._grid_details(data),
        "energy": self._energy_details(data),
        "status": self._status_details(data),
        "flow": data.get("industryCurrentFlowMapV2") or {},
}

    async def get_energy_snapshot(
        self,
        inverter_sn: str,
    ) -> EnergySnapshot:
        """
        Convert the normalized Solis status into Helios'
        common EnergySnapshot model.
        """

        status = await self.get_inverter_status(
            inverter_sn
        )

        power = status["power"]
        battery = status["battery"]
        grid = status["grid"]
        status_data = status["status"]

        # Grid power is already normalized to kW
        # in _grid_details().
        #
        # Solis:
        #   positive = importing from grid
        #   negative = exporting to grid
        grid_power_kw = power_value(
            grid.get("power_kw")
        )

        grid_import_kw = max(
            grid_power_kw,
            0.0,
        )

        grid_export_kw = max(
            -grid_power_kw,
            0.0,
        )

        return EnergySnapshot(
            timestamp=parse_timestamp(
                status_data.get(
                    "data_timestamp_local"
                )
            ),
            solar_power_kw=power_value(
                power.get("pv_power_kw")
            ),
            house_load_kw=power_value(
                power.get("home_load_kw")
            ),
            battery_soc_percent=power_value(
                battery.get("soc_percent")
            ),
            battery_power_kw=power_value(
                battery.get("power_kw_v2")
            ),
            grid_import_kw=round(
                grid_import_kw,
                3,
            ),
            grid_export_kw=round(
                grid_export_kw,
                3,
            ),
        )

    @staticmethod
    def _inverter_details(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "serial_number": data.get("sn"),
            "model": data.get("machine"),
            "product_model": data.get("productModel"),
            "collector_sn": data.get("collectorsn"),
            "firmware": {
                "version": data.get("version"),
                "version2": data.get("version2"),
                "hmi": data.get("hmiVersionAll"),
                "dsp": data.get("dspmVersionAll"),
            },
            "station": {
                "id": data.get("stationId"),
                "name": data.get("stationName"),
                "timezone": data.get("timeZoneStr"),
            },
        }

    @staticmethod
    def _power_details(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Normalize inverter power information.

        The S6-EH1P12K03-NV-YD-L is reporting dcPac as 0
        even though the MPPT inputs are producing power.

        Therefore PV power is calculated from the active
        MPPT power values.
        """

        pv_power_w = (
            power_value(data.get("mpptPow1"))
            + power_value(data.get("mpptPow2"))
            + power_value(data.get("mpptPow3"))
            + power_value(data.get("mpptPow4"))
        )

        pv_power_kw = pv_power_w / 1000.0

        return {
            "rated_power_kw": data.get("power"),

            # MPPT power is reported by Solis in watts.
            "pv_power_kw": round(
                pv_power_kw,
                3,
            ),

            "ac_power_kw": data.get("pac"),

            "home_load_kw": data.get(
                "familyLoadPowerV2"
            ),

            "home_load_kw_raw": data.get(
                "familyLoadPowerOrigin"
            ),

            "total_load_kw": data.get(
                "totalAndSmartLoadPowerOrigin"
            ),

            "battery_power_kw": data.get(
                "batteryPowerV2"
            ),

            "reactive_power_var": data.get(
                "reactivePower"
            ),

            "apparent_power_va": data.get(
                "apparentPower"
            ),
        }

    @staticmethod
    def _battery_details(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        batteries = data.get(
            "batteryList"
        ) or []

        first_battery = (
            batteries[0]
            if batteries
            else {}
        )

        # Solis top-level batteryPower / batteryPowerV2
        # may report 0 for this inverter.
        #
        # The actual Dyness battery telemetry is available
        # inside batteryList.
        #
        # batteryList[].batteryPower is reported in watts.
        #
        # Confirmed with live Dyness LV telemetry:
        #
        # Solis:
        #   positive = charging
        #   negative = discharging
        #
        # Helios uses the same convention:
        #   positive = charging
        #   negative = discharging

        nested_battery_power_w = first_battery.get(
            "batteryPower"
        )

        if nested_battery_power_w is not None:
            battery_power_kw = round(
        power_value(
                    nested_battery_power_w
                ) / 1000.0,
                3,
            )
        else:
            battery_power_kw = power_value(
                data.get("batteryPowerV2")
            )

        return {
            "count": data.get(
                "batteryNum",
                len(batteries),
            ),

            "type": (
                first_battery.get(
                    "batteryTypeName"
                )
                or data.get(
                    "batteryType"
                )
            ),

            "soc_percent": (
                first_battery.get(
                    "batteryCapacitySoc"
                )
                if first_battery
                else data.get(
                    "batteryCapacitySoc"
                )
            ),

            "soh_percent": (
                first_battery.get(
                    "batteryHealthSoh"
                )
                if first_battery
                else data.get(
                    "batteryHealthSoh"
                )
            ),

            "voltage_v": (
                first_battery.get(
                    "batteryVoltage"
                )
                if first_battery
                else data.get(
                    "batteryVoltage"
                )
            ),

            "current_a": (
                first_battery.get(
                    "bstteryCurrent"
                )
                if first_battery
                else data.get(
                    "bstteryCurrent"
                )
            ),

            "power_kw": battery_power_kw,
            "power_kw_v2": battery_power_kw,

            "charge_limit_a": (
                first_battery.get(
                    "batteryChargingCurrent"
                )
                if first_battery
                else data.get(
                    "batteryChargingCurrent"
                )
            ),

            "discharge_limit_a": (
                first_battery.get(
                    "batteryDischargeLimiting"
                )
                if first_battery
                else data.get(
                    "batteryDischargeLimiting"
                )
            ),

            "charge_energy": {
                "today_kwh": data.get(
                    "batteryTodayChargeEnergy"
                ),
                "month_kwh": data.get(
                    "batteryMonthChargeEnergy"
                ),
                "year_kwh": data.get(
                    "batteryYearChargeEnergy"
                ),
                "total_kwh": data.get(
                    "batteryTotalChargeEnergy"
                ),
            },

            "discharge_energy": {
                "today_kwh": data.get(
                    "batteryTodayDischargeEnergy"
                ),
                "month_kwh": data.get(
                    "batteryMonthDischargeEnergy"
                ),
                "year_kwh": data.get(
                    "batteryYearDischargeEnergy"
                ),
                "total_kwh": data.get(
                    "batteryTotalDischargeEnergy"
                ),
            },

            "bms": {
                "state": first_battery.get(
                    "bmsBmsState"
                ),
                "temperature_c": first_battery.get(
                    "bmsTemp"
                ),
                "battery_type": first_battery.get(
                    "batteryTypeName"
                ),
                "serial_number": first_battery.get(
                    "batterySn"
                ),
            },

            "limits": {
                "soc_discharge_percent": (
                    first_battery.get(
                        "socDischargeSet"
                    )
                    if first_battery
                    else data.get(
                        "socDischargeSet"
                    )
                ),

                "soc_charge_percent": (
                    first_battery.get(
                        "socChargingSet"
                    )
                    if first_battery
                    else data.get(
                        "socChargingSet"
                    )
                ),

                "max_charge_current_a": (
                    first_battery.get(
                        "batteryCMaxiSet"
                    )
                    if first_battery
                    else data.get(
                        "batteryCMaxiSet"
                    )
                ),

                "max_discharge_current_a": (
                    first_battery.get(
                        "batteryDMaxiSet"
                    )
                    if first_battery
                    else data.get(
                        "batteryDMaxiSet"
                    )
                ),
            },
        }

    @staticmethod
    def _grid_details(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        grid = data.get(
            "gridDetailVo"
        ) or {}

        # Solis reports grid power in watts.
        # Helios uses kW internally.
        raw_grid_power = power_value(
            grid.get("gridPower")
        )

        grid_power_kw = (
            raw_grid_power / 1000.0
        )

        return {
            "power_kw": round(
                grid_power_kw,
                3,
            ),

            "voltage_v": grid.get(
                "gridVoltageA"
            ),

            "current_a": grid.get(
                "gridCurrentA"
            ),

            "frequency_hz": (
                grid.get("gridFac")
                or data.get("fac")
            ),

            "reactive_power_var": grid.get(
                "gridReactivePower"
            ),

            "power_factor": grid.get(
                "gridPowerFactor"
            ),

            "energy": {
                "purchased_today_kwh": data.get(
                    "gridPurchasedTodayEnergy"
                ),
                "purchased_month_kwh": data.get(
                    "gridPurchasedMonthEnergy"
                ),
                "purchased_year_kwh": data.get(
                    "gridPurchasedYearEnergy"
                ),
                "purchased_total_kwh": data.get(
                    "gridPurchasedTotalEnergy"
                ),

                "sold_today_kwh": data.get(
                    "gridSellTodayEnergy"
                ),
                "sold_month_kwh": data.get(
                    "gridSellMonthEnergy"
                ),
                "sold_year_kwh": data.get(
                    "gridSellYearEnergy"
                ),
                "sold_total_kwh": data.get(
                    "gridSellTotalEnergy"
                ),
            },
        }

    @staticmethod
    def _energy_details(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "solar_generation": {
                "today_kwh": data.get(
                    "eToday"
                ),
                "month_kwh": data.get(
                    "eMonth"
                ),
                "year_kwh": data.get(
                    "eYear"
                ),
                "total_kwh": data.get(
                    "eTotal"
                ),
            },

            "home_load": {
                "today_kwh": data.get(
                    "homeLoadTodayEnergy"
                ),
                "month_kwh": data.get(
                    "homeLoadMonthEnergy"
                ),
                "year_kwh": data.get(
                    "homeLoadYearEnergy"
                ),
                "total_kwh": data.get(
                    "homeLoadTotalEnergy"
                ),
            },

            "grid": {
                "purchased_today_kwh": data.get(
                    "gridPurchasedTodayEnergy"
                ),
                "sold_today_kwh": data.get(
                    "gridSellTodayEnergy"
                ),
            },
        }

    @staticmethod
    def _status_details(
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        return {
            "state": data.get(
                "state"
            ),

            "current_state": data.get(
                "currentState"
            ),

            "fault_code": data.get(
                "faultCodeDesc"
            ),

            "alarm_level": data.get(
                "alarmLevel"
            ),

            "alarm_state": data.get(
                "alarmState"
            ),

            "warning_info": data.get(
                "warningInfoData"
            ),

            "state_exception": data.get(
                "stateExceptionFlag"
            ),

            "temperature_c": data.get(
                "inverterTemperature"
            ),

            "data_timestamp": data.get(
                "dataTimestamp"
            ),

            "data_timestamp_local": data.get(
                "dataTimestampStr"
            ),

            "time": data.get(
                "timeStr"
            ),
        }