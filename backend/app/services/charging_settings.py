import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.settings import settings


SETTINGS_FILE = settings.DATA_DIR / "charging_settings.json"


@dataclass
class ChargingSettings:
    mode: str = "solar"

    # Temporary simulation value until the real
    # Tesla Fleet API is connected.
    simulated_tesla_soc_percent: float = 40.0

    # Used by Trip Mode / Charge Now.
    target_soc_percent: Optional[float] = 80.0

    # Required for Trip Mode.
    departure_time: Optional[datetime] = None

    # Temporary Model Y-style simulation capacity.
    battery_capacity_kwh: float = 75.0


def load_charging_settings() -> ChargingSettings:
    """
    Load saved charging settings from disk.

    If no saved file exists yet, Helios uses the
    default ChargingSettings values.
    """

    if not SETTINGS_FILE.exists():
        return ChargingSettings()

    try:
        with SETTINGS_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        departure_time = data.get(
            "departure_time"
        )

        if departure_time:
            departure_time = (
                datetime.fromisoformat(
                    departure_time
                )
            )

        return ChargingSettings(
            mode=data.get(
                "mode",
                "solar",
            ),
            simulated_tesla_soc_percent=float(
                data.get(
                    "simulated_tesla_soc_percent",
                    40.0,
                )
            ),
            target_soc_percent=(
                float(
                    data[
                        "target_soc_percent"
                    ]
                )
                if data.get(
                    "target_soc_percent"
                )
                is not None
                else None
            ),
            departure_time=departure_time,
            battery_capacity_kwh=float(
                data.get(
                    "battery_capacity_kwh",
                    75.0,
                )
            ),
        )

    except (
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        #
        # If the file is corrupt or unreadable,
        # fail safely back to defaults.
        #
        return ChargingSettings()


def save_charging_settings(
    settings: ChargingSettings,
) -> None:
    """
    Persist charging settings to disk.
    """

    SETTINGS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = asdict(settings)

    if settings.departure_time:
        data["departure_time"] = (
            settings.departure_time.isoformat()
        )

    temporary_file = SETTINGS_FILE.with_suffix(".json.tmp")

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            indent=2,
        )

    # Atomic replacement prevents a partial JSON file if the
    # container is interrupted while settings are being saved.
    temporary_file.replace(SETTINGS_FILE)


charging_settings = (
    load_charging_settings()
)
