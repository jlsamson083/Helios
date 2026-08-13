import sqlite3
import shutil

from app.core.settings import PROJECT_ROOT, settings


DB_PATH = settings.DATABASE_PATH
LEGACY_DB_PATH = PROJECT_ROOT / "backend" / "helios.db"


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database() -> None:
    # Preserve history created before DATA_DIR became configurable.
    # copy2 leaves the legacy database untouched for easy rollback.
    if (
        not DB_PATH.exists()
        and LEGACY_DB_PATH.exists()
        and LEGACY_DB_PATH != DB_PATH
    ):
        DB_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        shutil.copy2(
            LEGACY_DB_PATH,
            DB_PATH,
        )

    connection = get_connection()

    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS energy_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                solar_power_kw REAL NOT NULL,
                house_load_kw REAL NOT NULL,
                battery_soc_percent REAL NOT NULL,
                battery_power_kw REAL NOT NULL,
                grid_import_kw REAL NOT NULL,
                grid_export_kw REAL NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_energy_snapshots_timestamp
            ON energy_snapshots(timestamp)
            """
        )

        connection.commit()

    finally:
        connection.close()
