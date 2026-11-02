import sqlite3

import pytest

from kairos.db import connect, init_db
from kairos.services.lists import (
    add_ticker,
    get_thesis,
    list_tickers,
    remove_ticker,
    set_shares,
    set_thesis,
)


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


def test_migration_adds_columns_to_old_db(settings):
    old = sqlite3.connect(settings.db_path)
    old.execute(
        "CREATE TABLE lists (list_name TEXT NOT NULL, ticker TEXT NOT NULL, added_at TEXT NOT NULL,"
        " PRIMARY KEY (list_name, ticker))"
    )
    old.execute("INSERT INTO lists VALUES ('holdings', 'VOO', '2026-01-01')")
    old.commit()
    old.close()
    conn = connect(settings.db_path)
    init_db(conn, settings)
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(lists)")}
    assert {"shares", "thesis"} <= cols
    assert list_tickers(conn, "holdings") == ["VOO"]


def test_set_shares_validation(conn):
    add_ticker(conn, "holdings", "NVDA")
    set_shares(conn, "nvda", 12.5)
    assert conn.execute("SELECT shares FROM lists WHERE ticker='NVDA'").fetchone()[0] == 12.5
    set_shares(conn, "NVDA", 0)
    assert conn.execute("SELECT shares FROM lists WHERE ticker='NVDA'").fetchone()[0] is None
    for bad in (-1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            set_shares(conn, "NVDA", bad)
    with pytest.raises(KeyError):
        set_shares(conn, "AAPL", 1)


def test_set_thesis_trims_and_limits(conn):
    add_ticker(conn, "watching", "SMH")
    set_thesis(conn, "watching", "SMH", "  AI demand \n")
    assert get_thesis(conn, "SMH") == "AI demand"
    with pytest.raises(ValueError, match="200 characters"):
        set_thesis(conn, "watching", "SMH", "x" * 201)
    set_thesis(conn, "watching", "SMH", "   ")
    assert get_thesis(conn, "SMH") is None
    with pytest.raises(KeyError):
        set_thesis(conn, "holdings", "SMH", "nope")
