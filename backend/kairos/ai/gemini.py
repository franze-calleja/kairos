import logging
from datetime import datetime
from typing import Literal

from google import genai
from google.genai import errors, types

from kairos.ai.budget import RequestBudget
from kairos.ai.schema import AISummary, Claim
from kairos.config import Settings

log = logging.getLogger(__name__)
GeminiStatus = Literal["ok", "budget_exhausted", "unavailable", "not_configured"]


def _client_factory(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def _valid(claims: list[Claim], allowed: set[str]) -> list[Claim]:
    return [c for c in claims if c.source_ids and set(c.source_ids) <= allowed]


async def summarize(
    settings: Settings,
    budget: RequestBudget,
    prompt: str,
    allowed_ids: set[str],
    now: datetime,
) -> tuple[AISummary | None, GeminiStatus]:
    if not settings.gemini_api_key:
        return None, "not_configured"
    client = _client_factory(settings.gemini_api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=AISummary
    )
    for _attempt in range(2):
        if not budget.try_acquire(now):
            return None, "budget_exhausted"
        try:
            response = await client.aio.models.generate_content(
                model=settings.gemini_model, contents=prompt, config=config
            )
        except errors.APIError as e:
            if e.code == 429:
                return None, "budget_exhausted"
            log.warning("Gemini API error %s: %s", e.code, e)
            continue
        except Exception as e:  # network errors, SDK parsing errors
            log.warning("Gemini call failed: %s", e)
            continue
        parsed = response.parsed
        if not isinstance(parsed, AISummary):
            continue
        drivers = _valid(parsed.drivers, allowed_ids)
        result = parsed.model_copy(
            update={
                "drivers": drivers,
                "bull_case": _valid(parsed.bull_case, allowed_ids),
                "bear_case": _valid(parsed.bear_case, allowed_ids),
                "not_enough_signal": parsed.not_enough_signal or not drivers,
            }
        )
        return result, "ok"
    return None, "unavailable"
