import pandas as pd


def make_df(closes: list[float], volume: float = 1_000_000, end: str = "2026-10-30") -> pd.DataFrame:
    idx = pd.bdate_range(end=end, periods=len(closes))
    return pd.DataFrame({"Close": closes, "Volume": [volume] * len(closes)}, index=idx)
