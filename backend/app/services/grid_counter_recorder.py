from datetime import datetime, timezone

from app.core.database import get_connection
from app.core.logger import logger
from app.core.settings import settings
from app.integrations.solis.service import SolisService


solis_service = SolisService()


async def record_grid_counters() -> None:
    """Persist lifetime Solis counters without controlling any device."""
    try:
        data = await solis_service.get_inverter_status(settings.SOLIS_INVERTER_SN)
        grid = data["grid"]["energy"]
        imported = float(grid["purchased_total_kwh"] or 0)
        exported = float(grid["sold_total_kwh"] or 0)
        timestamp = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        connection = get_connection()
        try:
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
    except Exception as exc:
        logger.warning(f"Unable to record Solis grid counters: {exc}")
