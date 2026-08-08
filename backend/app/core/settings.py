from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Helios"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    MIN_BATTERY_SOC: float = 30.0
    TESLA_CHARGER_VOLTAGE: float = 240.0
    TESLA_MAX_CURRENT: float = 48.0

class Config:
        env_file = ".env"


settings = Settings()
