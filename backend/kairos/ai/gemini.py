import asyncio
import logging
from datetime import UTC, datetime
from typing import Literal

from google import genai
from google.genai import errors, types

from kairos.ai.budget import RequestBudget
from kairos.ai.schema import AISummary, Claim
from kairos.config import Settings

log = logging.getLogger(__name__)
GeminiStatus = Literal["ok", "budget_exhausted", "unavailable", "not_configured"]
TIMEOUT_MS = 60_000
RATE_LIMIT_BACKOFF_SECONDS = 60.0
# Waits before the 2nd and 3rd attempt after Google reports overload (5xx) or the call fails.
TRANSIENT_BACKOFF_SECONDS = (5.0, 20.0)
MAX_PACING_WAIT_SECONDS = 70.0


def _clock() -> datetime:
    return datetime.now(UTC)


_sleep = asyncio.sleep


def _client_factory(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=TIMEOUT_MS))


async def _acquire(budget: RequestBudget) -> bool:
    """Wait for a per-minute slot if needed; False when the daily budget is used up."""
    wait = budget.seconds_until_slot(_clock())
    if wait is None or wait > MAX_PACING_WAIT_SECONDS:
        return False
    if wait > 0:
        await _sleep(wait)
    return budget.try_acquire(_clock())


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
    # Two tries on the main model, then one on the lighter fallback model (often less loaded).
    models = [settings.gemini_model, settings.gemini_model]
    models.append(settings.gemini_fallback_model or settings.gemini_model)
    rate_limited = False
    transient = False
    for attempt, model in enumerate(models):
        if transient:
            await _sleep(TRANSIENT_BACKOFF_SECONDS[attempt - 1])
        transient = False
        if not await _acquire(budget):
            return None, "budget_exhausted"
        try:
            response = await client.aio.models.generate_content(
                model=model, contents=prompt, config=config
            )
        except errors.APIError as e:
            if e.code == 429:
                if rate_limited:
                    return None, "budget_exhausted"
                rate_limited = True
                await _sleep(RATE_LIMIT_BACKOFF_SECONDS)
                continue
            transient = e.code >= 500
            log.warning("Gemini API error %s (model %s)", e.code, model)
            continue
        except Exception as e:  # network errors, timeouts, SDK parsing errors
            transient = True
            log.warning("Gemini call failed: %s (model %s)", type(e).__name__, model)
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
                "takeaway": next(iter(_valid([parsed.takeaway], allowed_ids)), None)
                if parsed.takeaway
                else None,
            }
        )
        return result, "ok"
    return None, "unavailable"
