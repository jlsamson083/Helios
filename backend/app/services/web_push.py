import json
from datetime import datetime, timezone

from pywebpush import WebPushException, webpush

from app.core.database import get_connection
from app.core.logger import logger
from app.core.settings import settings


def save_subscription(subscription: dict) -> None:
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO push_subscriptions
            (endpoint, p256dh, auth, created_at) VALUES (?, ?, ?, ?)
            """,
            (subscription["endpoint"], subscription["keys"]["p256dh"],
             subscription["keys"]["auth"], datetime.now(timezone.utc).isoformat()),
        )
        connection.commit()
    finally:
        connection.close()


def remove_subscription(endpoint: str) -> None:
    connection = get_connection()
    try:
        connection.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
        connection.commit()
    finally:
        connection.close()


def send_push_alert(alert: dict) -> dict:
    if not settings.VAPID_PRIVATE_KEY or not settings.VAPID_PUBLIC_KEY:
        return {"sent": 0, "failed": 0, "removed": 0}
    connection = get_connection()
    try:
        rows = connection.execute("SELECT * FROM push_subscriptions").fetchall()
    finally:
        connection.close()
    payload = json.dumps({"title": alert["title"], "body": alert["message"],
                          "url": "/alerts", "badge": 1})
    result = {"sent": 0, "failed": 0, "removed": 0}
    for row in rows:
        try:
            webpush(
                subscription_info={"endpoint": row["endpoint"],
                                   "keys": {"p256dh": row["p256dh"], "auth": row["auth"]}},
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.VAPID_SUBJECT},
                timeout=10,
            )
            result["sent"] += 1
        except WebPushException as exc:
            status = getattr(exc.response, "status_code", None)
            if status in (404, 410):
                remove_subscription(row["endpoint"])
                result["removed"] += 1
            else:
                logger.warning(f"Web Push delivery failed: HTTP {status or 'unknown'}")
                result["failed"] += 1
    return result
