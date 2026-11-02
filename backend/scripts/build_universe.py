"""Build kairos/data/universe.txt: S&P 500 tickers in Yahoo form, for Discover's spike scan.

Run manually, then commit the output:
    cd backend && uv run python scripts/build_universe.py

Nasdaq-100 members outside the S&P 500 (a small set) are not included: no free source with
an open, automation-friendly list was found. Add tickers by hand at the bottom if you want them.
"""

from datetime import date
from io import StringIO
from pathlib import Path

import httpx
import pandas as pd

OUT = Path(__file__).resolve().parent.parent / "kairos" / "data" / "universe.txt"
SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
HEADERS = {"User-Agent": "Kairos/0.1 universe builder (personal research tool)"}


def sp500() -> set[str]:
    html = httpx.get(SP500_URL, headers=HEADERS, timeout=30, follow_redirects=True).text
    for table in pd.read_html(StringIO(html)):
        if "Symbol" in table.columns:
            return {str(t).strip().upper().replace(".", "-") for t in table["Symbol"].dropna()}
    raise SystemExit(f"no 'Symbol' column found at {SP500_URL}")


def main() -> None:
    tickers = sp500()
    header = f"# generated {date.today().isoformat()} from Wikipedia: List of S&P 500 companies"
    OUT.write_text("\n".join([header, *sorted(tickers)]) + "\n")
    print(f"wrote {len(tickers)} tickers to {OUT}")


if __name__ == "__main__":
    main()
