"""Build kairos/data/sector_pe.json: median trailing P/E per sector across universe.txt.

Run manually (takes several minutes; Yahoo may throttle):
    cd backend && uv run python scripts/build_sector_pe.py
"""

import json
import statistics
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import yfinance as yf

DATA = Path(__file__).resolve().parent.parent / "kairos" / "data"


def main() -> None:
    tickers = [
        t.strip()
        for t in (DATA / "universe.txt").read_text().splitlines()
        if t.strip() and not t.startswith("#")
    ]
    by_sector: dict[str, list[float]] = defaultdict(list)
    failed = 0
    for i, ticker in enumerate(tickers, 1):
        try:
            info = yf.Ticker(ticker).info
            pe, sector = info.get("trailingPE"), info.get("sector")
            if sector and isinstance(pe, (int, float)) and 0 < pe < 1000:
                by_sector[sector].append(float(pe))
        except Exception:
            failed += 1
        if i % 50 == 0:
            print(f"{i}/{len(tickers)} processed, {failed} failed")
        time.sleep(0.2)
    out = {
        "generated": date.today().isoformat(),
        "method": "median trailingPE of S&P 500 + Nasdaq-100 members per Yahoo sector",
        "sectors": {s: round(statistics.median(v), 1) for s, v in sorted(by_sector.items()) if v},
    }
    (DATA / "sector_pe.json").write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {len(out['sectors'])} sectors; {failed} tickers failed")


if __name__ == "__main__":
    main()
