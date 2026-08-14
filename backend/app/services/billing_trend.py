from datetime import datetime
from zoneinfo import ZoneInfo


MANILA = ZoneInfo("Asia/Manila")


def calculate_daily_grid_deltas(
    rows,
    *,
    baseline_import_kwh: float,
    baseline_export_kwh: float,
) -> list:
    days = {}
    previous_import = baseline_import_kwh
    previous_export = baseline_export_kwh
    for row in rows:
        timestamp = datetime.fromisoformat(row["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=MANILA)
        day = timestamp.astimezone(MANILA).date().isoformat()
        imported = float(row["grid_import_total_kwh"])
        exported = float(row["grid_export_total_kwh"])
        bucket = days.setdefault(day, {"date": day, "import_kwh": 0.0, "export_kwh": 0.0})
        bucket["import_kwh"] += max(imported - previous_import, 0)
        bucket["export_kwh"] += max(exported - previous_export, 0)
        previous_import = imported
        previous_export = exported
    return [
        {
            **bucket,
            "import_kwh": round(bucket["import_kwh"], 3),
            "export_kwh": round(bucket["export_kwh"], 3),
        }
        for bucket in days.values()
    ]
