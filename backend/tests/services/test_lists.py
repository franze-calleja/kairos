from kairos.db import connect, init_db
from kairos.services.lists import add_ticker, list_tickers, remove_ticker


def test_seed_once(settings):
    settings.kairos_seed_holdings = ["VOO", "QQQ"]
    conn = connect(settings.db_path)
    init_db(conn, settings)
    assert list_tickers(conn, "holdings") == ["QQQ", "VOO"]
    remove_ticker(conn, "holdings", "QQQ")
    init_db(conn, settings)
    assert list_tickers(conn, "holdings") == ["VOO"]


def test_add_idempotent_and_normalized(conn):
    assert add_ticker(conn, "holdings", "nvda") == "NVDA"
    add_ticker(conn, "holdings", "NVDA")
    assert list_tickers(conn, "holdings") == ["NVDA"]


def test_lists_are_separate(conn):
    add_ticker(conn, "watching", "SMH")
    assert list_tickers(conn, "holdings") == []
    assert list_tickers(conn, "watching") == ["SMH"]
