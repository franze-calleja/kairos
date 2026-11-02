import pytest

from kairos.tickers import normalize_ticker


@pytest.mark.parametrize(
    "raw,expected",
    [("nvda", "NVDA"), (" $NVDA ", "NVDA"), ("BRK.B", "BRK-B"), ("^GSPC", "^GSPC")],
)
def test_normalize(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "DROP TABLE", "TOOLONGTICKER1", "a;b"])
def test_normalize_rejects(raw):
    with pytest.raises(ValueError):
        normalize_ticker(raw)
