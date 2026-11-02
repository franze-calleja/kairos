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
