from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "Helios"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Mount this directory to persistent storage in production.
    DATA_DIR: Path = PROJECT_ROOT / "backend" / "data"

    TESLA_CHARGER_VOLTAGE: float = 240.0
    TESLA_MAX_CURRENT: float = 32.0

    # Sprint 1 must never issue real Tesla vehicle commands.
    TESLA_SIMULATION_ONLY: bool = True

    MIN_BATTERY_SOC: float = 30.0

    SOLIS_BASE_URL: str = ""
    SOLIS_API_KEY_ID: str = ""
    SOLIS_API_SECRET: str = ""
    SOLIS_INVERTER_SN: str = ""

    @property
    def DATABASE_PATH(self) -> Path:
        return self.DATA_DIR / "helios.db"

    @model_validator(mode="after")
    def require_tesla_simulation(self) -> "Settings":
        if not self.TESLA_SIMULATION_ONLY:
            raise ValueError(
                "Tesla integration must remain simulation-only"
            )
        return self


settings = Settings()
