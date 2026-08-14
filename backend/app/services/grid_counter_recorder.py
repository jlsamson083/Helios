from datetime import datetime, timezone

from app.core.database import get_connection
from app.core.logger import logger
from app.core.settings import settings
from app.integrations.solis.service import SolisService
from app.services.alerts import create_alert


solis_service = SolisService()


async def record_grid_counters() -> None:
    """Persist lifetime Solis counters without controlling any device."""
    try:
        data = await solis_service.get_inverter_status(settings.SOLIS_INVERTER_SN)
        grid = data["grid"]["energy"]
        imported = float(grid["purchased_total_kwh"] or 0)
        exported = float(grid["sold_total_kwh"] or 0)
        grid_power_kw = float(data["grid"]["power_kw"] or 0)
        battery_soc = float(data["battery"]["soc_percent"] or 0)
        timestamp = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        connection = get_connection()
        try:
            previous = connection.execute(
                """
                SELECT grid_import_total_kwh, grid_export_total_kwh
                FROM solis_grid_counters ORDER BY timestamp DESC LIMIT 1
                """
            ).fetchone()
            connection.execute(
                """
                INSERT OR REPLACE INTO solis_grid_counters (
                    timestamp, grid_import_total_kwh, grid_export_total_kwh
                ) VALUES (?, ?, ?)
                """,
                (timestamp.isoformat(), imported, exported),
            )
            connection.commit()
        finally:
            connection.close()
        if grid_power_kw >= 0.5:
            create_alert(
                kind="grid_import",
                severity="warning",
                title="Grid import detected",
                message=f"Your home is currently importing {grid_power_kw:.2f} kW from the grid.",
                cooldown_minutes=60,
            )
        if previous:
            export_delta = max(exported - previous[1], 0)
            if export_delta >= 0.01:
                create_alert(
                    kind="grid_export",
                    severity="success",
                    title="Solar export recorded",
                    message=f"Solis measured {export_delta:.2f} kWh of new grid export.",
                    cooldown_minutes=60,
                )
        if battery_soc <= settings.MIN_BATTERY_SOC:
            create_alert(
                kind="low_battery",
                severity="critical",
                title="Battery reserve is low",
                message=f"Battery SOC is {battery_soc:.0f}%, at or below the {settings.MIN_BATTERY_SOC:.0f}% reserve.",
                cooldown_minutes=120,
            )
    except Exception as exc:
        logger.warning(f"Unable to record Solis grid counters: {exc}")
        try:
            create_alert(
                kind="solis_failure",
                severity="critical",
                title="Solis data unavailable",
                message="Helios could not refresh inverter data. It will retry automatically.",
                cooldown_minutes=60,
            )
        except Exception as alert_exc:
            logger.warning(f"Unable to record Solis failure alert: {alert_exc}")
