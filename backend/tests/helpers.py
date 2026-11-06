import pandas as pd


def make_df(
    closes: list[float], volume: float = 1_000_000, end: str = "2026-10-30"
) -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"Close": closes, "Volume": [volume] * len(closes)}, index=idx)


def series(n: int = 60, last: float = -9.3) -> list[float]:
    """n-1 closes alternating +0.5%/-0.5%, then a final move of `last` percent."""
    closes, p = [100.0], 100.0
    for i in range(n - 2):
        p *= 1.005 if i % 2 == 0 else 0.995
        closes.append(p)
    closes.append(p * (1 + last / 100))
    return closes
