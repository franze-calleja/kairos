from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"
    gemini_rpm: int = 10
    gemini_rpd: int = 200
    finnhub_api_key: str | None = None
    sec_user_agent: str | None = None
    reddit_enabled: bool = False
    reading_cache_hours: int = 4
    morning_refresh_time: str = "07:00"
    tz: str = "UTC"
    db_path: str = "data/kairos.db"
    scheduler_enabled: bool = True
    kairos_seed_holdings: Annotated[list[str], NoDecode] = []
    kairos_seed_watching: Annotated[list[str], NoDecode] = []
    news_window_days: int = 7

    # Hype thresholds
    micro_cap_usd: float = 300_000_000
    price_spike_pct: float = 30.0
    penny_price: float = 5.0
    low_volume: float = 100_000
    attention_ratio: float = 3.0
    attention_min_articles: int = 5

    @field_validator("kairos_seed_holdings", "kairos_seed_watching", mode="before")
    @classmethod
    def _split_tickers(cls, value: object) -> object:
        if isinstance(value, str):
            return [t.strip().upper() for t in value.split(",") if t.strip()]
        return value

    @field_validator("gemini_api_key", "finnhub_api_key", "sec_user_agent", mode="before")
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
