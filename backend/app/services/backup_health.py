import json
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.core.database import get_connection
from app.core.logger import logger
from app.core.settings import settings
from app.services.alerts import create_alert


MANILA = ZoneInfo("Asia/Manila")


def _parse_utc(value: object) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _next_run(now: datetime) -> datetime:
    local = now.astimezone(MANILA)
    candidate = local.replace(hour=18, minute=0, second=0, microsecond=0)
    if candidate <= local:
        candidate += timedelta(days=1)
    return candidate


def get_backup_status(*, now: Optional[datetime] = None) -> dict:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    status_path = settings.BACKUP_STATUS_PATH
    payload: dict = {}
    error = None
    try:
        with status_path.open(encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            raise ValueError("Backup status must be a JSON object")
        payload = loaded
    except FileNotFoundError:
        pass
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        error = str(exc)

    last_success = _parse_utc(payload.get("last_success_at"))
    age_hours = (
        (now - last_success).total_seconds() / 3600
        if last_success is not None
        else None
    )
    if error:
        health = "unavailable"
    elif last_success is None:
        health = "never_run"
    elif age_hours is not None and age_hours > settings.CLOUD_BACKUP_STALE_HOURS:
        health = "stale"
    else:
        health = "healthy"

    return {
        "status": health,
        "last_success_at": last_success.isoformat() if last_success else None,
        "age_hours": round(age_hours, 2) if age_hours is not None else None,
        "last_object": payload.get("last_object"),
        "size_bytes": payload.get("size_bytes"),
        "retention_count": payload.get("retention_count", 30),
        "stale_after_hours": settings.CLOUD_BACKUP_STALE_HOURS,
        "next_scheduled_at": _next_run(now).isoformat(),
        "error": error,
    }


def _previous_health() -> Optional[str]:
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT health FROM backup_monitor_state WHERE id = 1"
        ).fetchone()
        return row[0] if row else None
    finally:
        connection.close()


def _save_health(health: str, checked_at: str) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO backup_monitor_state (id, health, checked_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                health=excluded.health,
                checked_at=excluded.checked_at
            """,
            (health, checked_at),
        )
        connection.commit()
    finally:
        connection.close()


async def check_backup_health() -> dict:
    status = get_backup_status()
    current = status["status"]
    previous = _previous_health()

    if current == "stale" and previous != "stale":
        create_alert(
            kind="cloud_backup_stale",
            severity="critical",
            title="Helios cloud backup is overdue",
            message=(
                "No successful encrypted cloud backup has completed for more "
                f"than {settings.CLOUD_BACKUP_STALE_HOURS:g} hours."
            ),
            cooldown_minutes=60,
        )
    elif current == "healthy" and previous == "stale":
        create_alert(
            kind="cloud_backup_recovered",
            severity="info",
            title="Helios cloud backups recovered",
            message="Encrypted daily backups are working again.",
            cooldown_minutes=1,
        )

    try:
        _save_health(current, datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        logger.warning(f"Unable to save backup monitor state: {exc}")
    return status
