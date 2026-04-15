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
    enable_aisstream: bool = True
    aisstream_api_key: str | None = None
    aisstream_bounding_boxes_json: str = "[[[-90,-180],[90,180]]]"
    aisstream_filter_message_types_json: str = "[]"
    aisstream_stall_threshold_seconds: int = 90
    enable_aishub: bool = False
    aishub_username: str | None = None
    aishub_password: str | None = None
    aishub_poll_interval_seconds: int = 60
    enable_gfw: bool = False
    gfw_api_token: str | None = None
    gfw_poll_interval_seconds: int = 3600
    enable_eonet: bool = True
    eonet_default_status: str = "open"
    eonet_default_days: int = 30
    eonet_poll_interval_seconds: int = 900
    eonet_use_geojson: bool = True
    enable_firms: bool = True
    firms_map_key: str | None = None
    firms_poll_interval_seconds: int = 300
    firms_default_lookback_days: int = 2
    firms_enable_clustering: bool = True
    enable_nws: bool = True
    nws_poll_interval_seconds: int = 300
    nws_alerts_only: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
