from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gemini_api_key: str | None = None
    gemini_model: str = "gemini-flash-latest"
    gemini_fallback_model: str | None = "gemini-flash-lite-latest"
    gemini_rpm: int = 10
    gemini_rpd: int = 200
    finnhub_api_key: str | None = None
    sec_user_agent: str | None = None
    reddit_enabled: bool = False
    reading_cache_hours: int = 4
    morning_refresh_time: str = "07:00"
    evening_refresh_time: str | None = "21:00"  # readings only, before the US open; empty disables
    tz: str = "UTC"
    db_path: str = "data/kairos.db"
    backup_dir: str | None = "backups"  # daily copies of the database; empty turns backups off
    backup_keep: int = Field(default=14, ge=1)
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

    @model_validator(mode="after")
    def _evening_after_morning(self) -> Settings:
        # HH:MM strings compare correctly as text. Morning is due until evening starts.
        if self.evening_refresh_time and self.evening_refresh_time <= self.morning_refresh_time:
            raise ValueError(
                "EVENING_REFRESH_TIME must be later than MORNING_REFRESH_TIME "
                f"(got {self.evening_refresh_time} vs {self.morning_refresh_time}); "
                "leave it empty to turn the evening refresh off"
            )
        return self

    @field_validator("kairos_seed_holdings", "kairos_seed_watching", mode="before")
    @classmethod
    def _split_tickers(cls, value: object) -> object:
        from kairos.tickers import normalize_ticker

        if isinstance(value, str):
            value = [t for t in value.split(",") if t.strip()]
        if isinstance(value, list):
            return [normalize_ticker(str(t)) for t in value]  # ValueError -> clear message
        return value

    @field_validator("tz")
    @classmethod
    def _valid_tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(
                f"Unknown timezone {value!r}; use an IANA name like Asia/Manila"
            ) from e
        return value

    @field_validator("morning_refresh_time", "evening_refresh_time", mode="before")
    @classmethod
    def _valid_time(cls, value: object, info) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            if info.field_name == "morning_refresh_time":
                raise ValueError("MORNING_REFRESH_TIME must be HH:MM, e.g. 07:00")
            return None
        text = str(value).strip()
        parts = text.split(":")
        ok = len(parts) == 2 and all(p.isdigit() for p in parts)
        if not ok or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
            raise ValueError(f"{info.field_name.upper()} {text!r} must be HH:MM, e.g. 07:00")
        return text

    @field_validator(
        "gemini_api_key",
        "finnhub_api_key",
        "sec_user_agent",
        "gemini_fallback_model",
        "backup_dir",
        mode="before",
    )
    @classmethod
    def _blank_is_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
