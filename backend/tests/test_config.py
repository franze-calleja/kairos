import pytest
from pydantic import ValidationError

from kairos.config import Settings


def test_seed_lists_parse_comma_separated(monkeypatch):
    monkeypatch.setenv("KAIROS_SEED_HOLDINGS", "voo, qqq,NVDA")
    assert Settings(_env_file=None).kairos_seed_holdings == ["VOO", "QQQ", "NVDA"]


def test_seed_lists_default_empty(monkeypatch):
    monkeypatch.delenv("KAIROS_SEED_HOLDINGS", raising=False)
    monkeypatch.delenv("KAIROS_SEED_WATCHING", raising=False)
    s = Settings(_env_file=None)
    assert s.kairos_seed_holdings == []
    assert s.kairos_seed_watching == []


def test_defaults():
    s = Settings(_env_file=None)
    assert s.gemini_rpm == 10
    assert s.gemini_rpd == 200
    assert s.reading_cache_hours == 4
    assert s.reddit_enabled is False
    assert s.gemini_model == "gemini-flash-latest"
    assert s.gemini_fallback_model == "gemini-flash-lite-latest"


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("tz", "Mars/Olympus", "Unknown timezone"),
        ("morning_refresh_time", "7am", "HH:MM"),
        ("morning_refresh_time", "25:00", "HH:MM"),
        ("kairos_seed_holdings", "VOO;QQQ", "Invalid ticker"),
    ],
)
def test_bad_config_gives_clear_message(field, value, message):
    with pytest.raises(ValidationError, match=message):
        Settings(_env_file=None, **{field: value})


def test_seed_tickers_are_normalized():
    assert Settings(_env_file=None, kairos_seed_watching="brk.b, $nvda").kairos_seed_watching == [
        "BRK-B",
        "NVDA",
    ]
