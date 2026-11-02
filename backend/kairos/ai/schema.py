from typing import Literal

from pydantic import BaseModel


class Claim(BaseModel):
    text: str
    source_ids: list[str]


class AISummary(BaseModel):
    lean: Literal["bullish", "neutral", "bearish"]
    confidence: Literal["low", "medium", "high"]
    not_enough_signal: bool
    substantive_news: bool
    drivers: list[Claim]
    bull_case: list[Claim]
    bear_case: list[Claim]
    takeaway: Claim | None = None  # one-sentence synthesis shown at the top of a reading
