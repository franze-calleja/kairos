import re

from kairos.adapters.base import strip_html
from kairos.models import NewsItem

_NON_WORD = re.compile(r"[^a-z0-9 ]+")


def _title_key(title: str) -> str:
    return " ".join(_NON_WORD.sub("", title.lower()).split())


def clean_news(
    items: list[NewsItem], max_items: int = 40, summary_chars: int = 400
) -> list[NewsItem]:
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    out: list[NewsItem] = []
    for item in items:
        title = strip_html(item.title)
        key = _title_key(title)
        if not key or item.id in seen_ids or key in seen_titles:
            continue
        seen_ids.add(item.id)
        seen_titles.add(key)
        summary = strip_html(item.summary)[:summary_chars]
        out.append(item.model_copy(update={"title": title, "summary": summary}))
    out.sort(key=lambda n: (-n.weight, -n.published_at.timestamp()))
    return out[:max_items]
