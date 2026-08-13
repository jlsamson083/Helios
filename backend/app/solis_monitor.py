import asyncio
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict

from app.integrations.solis.service import SolisService


INVERTER_SN = "1031270264300026"
REFRESH_SECONDS = 10

PH_TIMEZONE = timezone(timedelta(hours=8))


def clear_screen() -> None:
    os.system("clear")


def fmt(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "N/A"

    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return str(value)


def get_ph_time() -> str:
    return datetime.now(PH_TIMEZONE).strftime(
        "%Y-%m-%d %H:%M:%S (UTC+08:00)"
    )


def print_dashboard(data: Dict[str, Any]) -> None:
    clear_screen()

    inverter = data.get("inverter", {})
    power = data.get("power", {})
    battery = data.get("battery", {})
    grid = data.get("grid", {})
    status = data.get("status", {})

    snapshot_time = (
        status.get("data_timestamp_local")
        or status.get("time")
        or "N/A"
    )

    solar = float(power.get("pv_power_kw") or 0)
    house_load = float(power.get("home_load_kw") or 0)
    battery_power = float(battery.get("power_kw_v2") or 0)
    battery_soc = float(battery.get("soc_percent") or 0)
    grid_power = float(grid.get("power_kw") or 0)

    # Solis convention currently used by Helios:
    # positive grid power = importing
    # negative grid power = exporting
    grid_import = max(grid_power, 0)
    grid_export = max(-grid_power, 0)

    solar_surplus = max(solar - house_load, 0)

    min_battery_soc = 30.0
    tesla_max_current = 32.0
    tesla_voltage = 240.0

    if solar_surplus <= 0:
        tesla_allowed = False
        tesla_current = 0.0
        tesla_reason = "No solar surplus available"

    elif battery_soc < min_battery_soc:
        tesla_allowed = False
        tesla_current = 0.0
        tesla_reason = (
            f"Battery SOC {battery_soc:.1f}% "
            f"is below minimum {min_battery_soc:.1f}%"
        )

    else:
        tesla_allowed = True

        available_current = (
            solar_surplus * 1000
        ) / tesla_voltage

        tesla_current = min(
            available_current,
            tesla_max_current,
        )

        tesla_reason = "Solar surplus available"

    if battery_power > 0:
        battery_status = "CHARGING"
    elif battery_power < 0:
        battery_status = "DISCHARGING"
    else:
        battery_status = "IDLE"

    if grid_import > 0:
        grid_status = "IMPORTING"
    elif grid_export > 0:
        grid_status = "EXPORTING"
    else:
        grid_status = "BALANCED"

    print("╔══════════════════════════════════════════════════╗")
    print("║              HELIOS ENERGY MONITOR              ║")
    print("╠══════════════════════════════════════════════════╣")
    print(
        f"║ Inverter: {str(inverter.get('serial_number', 'N/A')):<35}║"
    )
    print(
        f"║ Model:    {str(inverter.get('model', 'N/A')):<35}║"
    )
    print("╠══════════════════════════════════════════════════╣")
    print("║ SOLAR                                            ║")
    print(
        f"║   Generation:              {fmt(solar):>8} kW        ║"
    )
    print(
        f"║   House Load:              {fmt(house_load):>8} kW        ║"
    )
    print(
        f"║   Solar Surplus:           {fmt(solar_surplus):>8} kW        ║"
    )
    print("╠══════════════════════════════════════════════════╣")
    print("║ BATTERY                                          ║")
    print(
        f"║   SOC:                     {fmt(battery_soc, 1):>8} %        ║"
    )
    print(
        f"║   Power:                   {fmt(battery_power):>8} kW        ║"
    )
    print(
        f"║   Status:                  {battery_status:<18}║"
    )
    print("╠══════════════════════════════════════════════════╣")
    print("║ GRID                                             ║")
    print(
        f"║   Import:                  {fmt(grid_import):>8} kW        ║"
    )
    print(
        f"║   Export:                  {fmt(grid_export):>8} kW        ║"
    )
    print(
        f"║   Status:                  {grid_status:<18}║"
    )
    print("╠══════════════════════════════════════════════════╣")
    print("║ TESLA                                            ║")
    print(
        f"║   Charging Allowed:        {'YES' if tesla_allowed else 'NO':>8}          ║"
    )
    print(
        f"║   Available Solar:         {fmt(solar_surplus):>8} kW        ║"
    )
    print(
        f"║   Charging Current:        {fmt(tesla_current, 1):>8} A         ║"
    )
    print(
        f"║   Reason: {tesla_reason:<39}║"
    )
    print("╠══════════════════════════════════════════════════╣")
    print(
        f"║ Solis Data: {str(snapshot_time):<33}║"
    )
    print(
        f"║ Monitor:    {get_ph_time():<33}║"
    )
    print("╚══════════════════════════════════════════════════╝")
    print()
    print(
        f"Refreshing every {REFRESH_SECONDS} seconds... "
        "Press Ctrl+C to stop."
    )


async def main() -> None:
    service = SolisService()

    while True:
        try:
            data = await service.get_inverter_status(INVERTER_SN)
            print_dashboard(data)

        except KeyboardInterrupt:
            print("\nHelios monitor stopped.")
            break

        except Exception as exc:
            clear_screen()

            print("╔══════════════════════════════════════════════════╗")
            print("║              HELIOS ENERGY MONITOR              ║")
            print("╠══════════════════════════════════════════════════╣")
            print("║ ERROR                                            ║")
            print("╠══════════════════════════════════════════════════╣")

            error_text = str(exc)
            print(f"║ {error_text[:48]:<48} ║")

            print("╚══════════════════════════════════════════════════╝")
            print()
            print(
                f"Retrying in {REFRESH_SECONDS} seconds..."
            )

        await asyncio.sleep(REFRESH_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
