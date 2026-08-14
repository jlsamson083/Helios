from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.database import get_connection
from app.services.web_push import send_push_alert


def create_alert(
    *,
    kind: str,
    severity: str,
    title: str,
    message: str,
    cooldown_minutes: int = 60,
) -> Optional[dict]:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=cooldown_minutes)
    connection = get_connection()
    try:
        duplicate = connection.execute(
            """
            SELECT id FROM alert_events
            WHERE kind = ? AND created_at >= ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (kind, cutoff.isoformat()),
        ).fetchone()
        if duplicate:
            return None
        cursor = connection.execute(
            """
            INSERT INTO alert_events (
                kind, severity, title, message, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (kind, severity, title, message, now.isoformat()),
        )
        connection.commit()
        alert = get_alert(cursor.lastrowid, connection=connection)
    finally:
        connection.close()
    if alert:
        send_push_alert(alert)
    return alert


def get_alert(alert_id: int, *, connection=None) -> Optional[dict]:
    owns_connection = connection is None
    connection = connection or get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM alert_events WHERE id = ?", (alert_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        if owns_connection:
            connection.close()


def list_alerts(limit: int = 100) -> dict:
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT * FROM alert_events
            ORDER BY created_at DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        unread = connection.execute(
            "SELECT COUNT(*) FROM alert_events WHERE read_at IS NULL"
        ).fetchone()[0]
        return {"items": [dict(row) for row in rows], "unread_count": unread}
    finally:
        connection.close()


def mark_alert_read(alert_id: int) -> Optional[dict]:
    connection = get_connection()
    try:
        connection.execute(
            """
            UPDATE alert_events SET read_at = COALESCE(read_at, ?)
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), alert_id),
        )
        connection.commit()
        return get_alert(alert_id, connection=connection)
    finally:
        connection.close()


def mark_all_alerts_read() -> int:
    connection = get_connection()
    try:
        cursor = connection.execute(
            "UPDATE alert_events SET read_at = ? WHERE read_at IS NULL",
            (datetime.now(timezone.utc).isoformat(),),
        )
        connection.commit()
        return cursor.rowcount
    finally:
        connection.close()
