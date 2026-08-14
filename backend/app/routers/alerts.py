from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl

from app.core.settings import settings
from app.services.alerts import list_alerts, mark_alert_read, mark_all_alerts_read
from app.services.web_push import save_subscription
from app.services.web_push import send_push_alert


router = APIRouter()


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscription(BaseModel):
    endpoint: HttpUrl
    keys: PushKeys


@router.get("/push-config")
def push_config():
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@router.post("/push-subscriptions", status_code=204)
def subscribe(subscription: PushSubscription):
    save_subscription(subscription.model_dump(mode="json"))


@router.post("/test-notification")
def test_notification():
    return send_push_alert({
        "title": "Helios notifications are ready",
        "message": "Your iPhone can receive Solis and grid-import alerts.",
    })


@router.get("")
def alerts(limit: int = Query(default=100, ge=1, le=200)):
    return list_alerts(limit)


@router.put("/read-all")
def read_all_alerts():
    return {"updated": mark_all_alerts_read()}


@router.put("/{alert_id}/read")
def read_alert(alert_id: int):
    alert = mark_alert_read(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
