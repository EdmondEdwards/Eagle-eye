from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Eagle Eye"
    database_url: str
    redis_url: str
    retention_days: int = 7
    live_channel: str = "eagle-eye:live"
    enable_satellites: bool = True
    satellite_default_source: str = "celestrak"
    celestrak_group: str = "active"
    spacetrack_username: str | None = None
    spacetrack_password: str | None = None
    n2yo_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
