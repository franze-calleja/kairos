import json
from typing import Any

from kairos.models import NewsItem

INSTRUCTIONS = """You are a careful equity research assistant for a long-term retail investor.
Write a short, evidence-based reading of {ticker} ({name}, {kind}).

Rules:
- Use only the listed articles below as evidence. Do not use outside knowledge of recent events.
- Every claim (drivers, bull_case, bear_case) must cite the ids of the articles that support it
  in source_ids, using the ids exactly as shown in square brackets.
- Give 2-5 drivers: the main things moving sentiment right now.
- Write takeaway: one plain sentence (max 25 words) that sums up the overall picture for a
  long-term investor, with the ids of the articles it rests on. Do not just repeat a driver.
- Do not state any number that does not appear in the articles or in the computed data.
- Set substantive_news=true only if the articles contain real company or fund developments
  (earnings, guidance, products, regulation, filings, analyst actions); false if they are mostly
  price chatter, hype or generic market commentary.
- If the evidence is too thin or too mixed to form a view, set not_enough_signal=true,
  lean="neutral" and confidence="low".
- This is research input, not financial advice. Do not tell the reader to buy or sell.

Computed data (calculated from market data, trustworthy):
{computed}

Articles:
{articles}
"""


def build_prompt(
    ticker: str, name: str, kind: str, news: list[NewsItem], computed: dict[str, Any]
) -> str:
    articles = "\n".join(
        f"[{n.id}] ({n.source}, {n.published_at:%Y-%m-%d}, {n.weight:.2f}) {n.title} — {n.summary}"
        for n in news
    )
    return INSTRUCTIONS.format(
        ticker=ticker,
        name=name,
        kind=kind,
        computed=json.dumps(computed, default=str, indent=1),
        articles=articles,
    )
