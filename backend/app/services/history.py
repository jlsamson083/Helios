from typing import List

from app.core.database import get_connection
from app.models.energy import EnergySnapshot


def save_energy_snapshot(
    snapshot: EnergySnapshot,
) -> bool:
    """
    Save an energy snapshot if its Solis timestamp
    has not already been stored.

    Returns True when a new snapshot is inserted.
    Returns False when the timestamp already exists.
    """

    connection = get_connection()

    try:
        timestamp = snapshot.timestamp.isoformat()

        existing = connection.execute(
            """
            SELECT 1
            FROM energy_snapshots
            WHERE timestamp = ?
            LIMIT 1
            """,
            (timestamp,),
        ).fetchone()

        if existing:
            return False

        connection.execute(
            """
            INSERT INTO energy_snapshots (
                timestamp,
                solar_power_kw,
                house_load_kw,
                battery_soc_percent,
                battery_power_kw,
                grid_import_kw,
                grid_export_kw
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                snapshot.solar_power_kw,
                snapshot.house_load_kw,
                snapshot.battery_soc_percent,
                snapshot.battery_power_kw,
                snapshot.grid_import_kw,
                snapshot.grid_export_kw,
            ),
        )

        connection.commit()

        return True

    finally:
        connection.close()


def get_energy_snapshots(
    limit: int = 500,
) -> List[dict]:
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                timestamp,
                solar_power_kw,
                house_load_kw,
                battery_soc_percent,
                battery_power_kw,
                grid_import_kw,
                grid_export_kw
            FROM energy_snapshots
            ORDER BY timestamp ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        connection.close()