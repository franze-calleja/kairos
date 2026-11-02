import re

_VALID = re.compile(r"^[A-Z0-9^-]{1,10}$")


def normalize_ticker(raw: str) -> str:
    """Normalize user input to Yahoo-style ticker form (e.g. ' $brk.b ' -> 'BRK-B')."""
    value = raw.strip().lstrip("$").strip().upper().replace(".", "-")
    if not value:
        raise ValueError("Empty ticker")
    if not _VALID.match(value):
        raise ValueError(f"Invalid ticker: {raw}")
    return value
