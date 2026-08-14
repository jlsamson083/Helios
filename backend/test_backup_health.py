import json
from datetime import datetime, timedelta, timezone

from app.services import backup_health


def test_backup_status_is_healthy_for_recent_success(tmp_path, monkeypatch):
    now = datetime(2026, 8, 14, 4, 0, tzinfo=timezone.utc)
    status_path = tmp_path / "cloud_backup_status.json"
    status_path.write_text(json.dumps({
        "last_success_at": (now - timedelta(hours=2)).isoformat(),
        "last_object": "daily/helios.enc",
        "size_bytes": 7312,
        "retention_count": 30,
    }))
    monkeypatch.setattr(backup_health.settings, "CLOUD_BACKUP_STATUS_PATH", status_path)

    result = backup_health.get_backup_status(now=now)

    assert result["status"] == "healthy"
    assert result["age_hours"] == 2
    assert result["last_object"] == "daily/helios.enc"
    assert result["next_scheduled_at"] == "2026-08-14T18:00:00+08:00"


def test_backup_status_becomes_stale_after_26_hours(tmp_path, monkeypatch):
    now = datetime(2026, 8, 14, 4, 0, tzinfo=timezone.utc)
    status_path = tmp_path / "cloud_backup_status.json"
    status_path.write_text(json.dumps({
        "last_success_at": (now - timedelta(hours=27)).isoformat(),
    }))
    monkeypatch.setattr(backup_health.settings, "CLOUD_BACKUP_STATUS_PATH", status_path)

    result = backup_health.get_backup_status(now=now)

    assert result["status"] == "stale"
    assert result["age_hours"] == 27


def test_missing_backup_status_has_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(
        backup_health.settings,
        "CLOUD_BACKUP_STATUS_PATH",
        tmp_path / "missing.json",
    )

    assert backup_health.get_backup_status()["status"] == "never_run"


def test_monitor_alerts_once_then_sends_recovery(monkeypatch):
    observed = []
    previous = {"health": "healthy"}

    monkeypatch.setattr(backup_health, "get_backup_status", lambda: {"status": "stale"})
    monkeypatch.setattr(backup_health, "_previous_health", lambda: previous["health"])
    monkeypatch.setattr(
        backup_health,
        "_save_health",
        lambda health, checked_at: previous.update(health=health),
    )
    monkeypatch.setattr(
        backup_health,
        "create_alert",
        lambda **kwargs: observed.append(kwargs),
    )

    import asyncio

    asyncio.run(backup_health.check_backup_health())
    asyncio.run(backup_health.check_backup_health())
    assert [item["kind"] for item in observed] == ["cloud_backup_stale"]

    monkeypatch.setattr(backup_health, "get_backup_status", lambda: {"status": "healthy"})
    asyncio.run(backup_health.check_backup_health())
    assert [item["kind"] for item in observed] == [
        "cloud_backup_stale",
        "cloud_backup_recovered",
    ]
