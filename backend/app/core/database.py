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
            CREATE TABLE IF NOT EXISTS billing_profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                billing_period TEXT NOT NULL,
                period_end TEXT NOT NULL,
                consumption_kwh REAL NOT NULL,
                energy_amount_php REAL NOT NULL,
                other_charges_php REAL NOT NULL,
                total_amount_php REAL NOT NULL,
                previous_meter_reading REAL NOT NULL,
                current_meter_reading REAL NOT NULL,
                import_rate_php_per_kwh REAL NOT NULL,
                export_rate_php_per_kwh REAL,
                updated_at TEXT NOT NULL
            )
            """
        )
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(billing_profile)")
        }
        for name in (
            "baseline_grid_import_kwh",
            "baseline_grid_export_kwh",
            "baseline_at",
            "confirmed_grid_import_kwh",
            "confirmed_grid_export_kwh",
            "confirmed_meter_reading",
            "confirmed_at",
            "next_meter_reading_date",
            "carried_credit_php",
        ):
            if name not in columns:
                column_type = "TEXT" if name in (
                    "baseline_at", "confirmed_at", "next_meter_reading_date"
                ) else "REAL"
                connection.execute(
                    f"ALTER TABLE billing_profile ADD COLUMN {name} {column_type}"
                )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_energy_snapshots_timestamp
            ON energy_snapshots(timestamp)
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS solis_grid_counters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL UNIQUE,
                grid_import_total_kwh REAL NOT NULL,
                grid_export_total_kwh REAL NOT NULL
            )
            """
        )

        connection.commit()

    finally:
        connection.close()
