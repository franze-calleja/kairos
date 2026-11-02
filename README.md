# Kairos

*Greek: "the right moment."*

Kairos is a self-hosted, AI-assisted research tool for US stocks and ETFs. For any ticker it reads recent news, SEC filings and market data and gives you a short, **sourced reading**:

- **Lean**: bullish / neutral / bearish, with a confidence level (or "not enough signal" when the evidence is thin)
- **What's driving it**, plus a **bull case** and a **bear case**. Every claim links to the article it came from.
- **Should I add more?**: price vs its 50- and 200-day averages, distance from the 52-week high, volatility
- **Upcoming events**: earnings, ex-dividend dates, Fed meetings and CPI releases
- **Hype check**: warning signs typical of pumped tickers (buzz without news, tiny company, sudden spikes, OTC listing, penny price, thin trading)
- **Quick numbers**: valuation and growth for stocks; fees, size and top holdings for ETFs
- **Track record**: how past leans turned out 1, 5 and 20 trading days later, compared with VOO
- **Discover**: tickers worth a look, from news spikes and funds or stocks similar to what you hold

All numbers are computed in code from market data. The AI (Gemini) only summarizes the supplied articles, must cite them, and never invents figures.

> **Kairos is a research tool, not financial advice.** Treat its readings as one input to your own research.

## What it is not

- Not a price predictor: there are no price targets and no "buy now" signals.
- Not a trading bot, and not connected to any broker.
- Not a hosted service: you run it yourself with your own free API keys.

## Quickstart

You need Docker (Docker Desktop on Mac/Windows).

1. **Get free keys**
   - Gemini API key: <https://aistudio.google.com/> (free tier)
   - Finnhub API key: <https://finnhub.io/> (free tier; used for company news, earnings dates and Discover)
2. **Configure**
   ```bash
   cp .env.example .env
   # edit .env: GEMINI_API_KEY, FINNHUB_API_KEY, SEC_USER_AGENT="Kairos you@example.com", TZ=Your/Timezone
   # optional: KAIROS_SEED_HOLDINGS=VOO,QQQ,NVDA to pre-fill your lists on first start
   ```
3. **Run**
   ```bash
   docker compose up -d
   ```
4. Open <http://localhost:8000>.

Kairos still runs without keys, with less: no Gemini key means no AI summary (the numbers still work); no Finnhub key means news comes from Google News only and the Discover news-spike scan is skipped. The **Data health** panel on each reading shows what was available.

## Configuration

All settings live in `.env` (see `.env.example` for the full list with comments).

| Variable | Default | What it does |
|---|---|---|
| `GEMINI_API_KEY` | — | Enables AI summaries |
| `GEMINI_MODEL` | `gemini-flash-latest` | Change if Google retires a model from the free tier |
| `GEMINI_RPM` / `GEMINI_RPD` | `10` / `200` | Request budget, kept below your free-tier limits (check AI Studio) |
| `FINNHUB_API_KEY` | — | Company news, earnings calendar, Discover spike scan |
| `SEC_USER_AGENT` | — | Required by SEC EDGAR, e.g. `Kairos you@example.com` |
| `REDDIT_ENABLED` | `false` | Optional low-volume Reddit RSS (see below) |
| `TZ` | `UTC` | Your timezone (IANA name, e.g. `Asia/Manila`) |
| `MORNING_REFRESH_TIME` | `07:00` | Daily automatic refresh of your lists, in `TZ` |
| `READING_CACHE_HOURS` | `4` | How long a reading is reused before it is rebuilt |
| `NEWS_WINDOW_DAYS` | `7` | Days of news read per ticker |
| `KAIROS_SEED_HOLDINGS` / `KAIROS_SEED_WATCHING` | empty | Comma-separated tickers to pre-fill lists on first start |
| Hype thresholds | see `.env.example` | Micro-cap, price spike, penny price, low volume, attention spike |

After changing `.env`, run `docker compose up -d` again to apply it.

## How a reading is made

1. Fetch news (Finnhub, Google News RSS), SEC filings (8-K/10-Q/10-K) and prices (Yahoo, via `yfinance`). ETFs are read through their top ~10 holdings, weighted by fund weight, plus general market news.
2. De-duplicate and trim the articles.
3. Compute price context, events, hype flags and quick numbers in code.
4. Make **one** Gemini request with the articles and computed data, asking for structured output that cites article IDs. Claims citing unknown sources are dropped. With fewer than 3 articles, no AI request is made.
5. Store the reading (SQLite) for caching and the track record.

Your holdings and watchlist are **never** sent to Gemini; only public market data is.

## Data sources and their terms

| Source | Used for | Notes |
|---|---|---|
| Yahoo Finance via `yfinance` | prices, company and fund data | Unofficial; can break when Yahoo changes. Personal use. |
| Finnhub | company news, earnings calendar | Free tier, 60 requests/min (Kairos paces to 1/sec) |
| Google News RSS | news | No key |
| SEC EDGAR | filings | Requires a descriptive User-Agent with contact email |
| Gemini API | summaries | Free-tier prompts may be used by Google to improve its products; only public data is sent |
| Reddit RSS (optional) | mentions | Reddit restricted new API access in 2025–2026; Kairos works fully without it |

Kairos ships **no** market data: everyone who runs it fetches data with their own keys.

## Backups

Your lists, readings and track record live in the `kairos-data` Docker volume.

```bash
# back up
docker compose cp kairos:/app/data/kairos.db ./kairos-backup.db
# restore (with Kairos stopped)
docker compose stop && docker compose cp ./kairos-backup.db kairos:/app/data/kairos.db && docker compose start
```

## Development

```bash
# backend (Python 3.14, uv)
cd backend
uv sync
uv run pytest
uv run ruff check . && uv run ruff format .
DB_PATH=../data/dev.db uv run uvicorn kairos.api.app:create_app --factory --reload

# frontend (Node 24, Vite dev server proxies /api to :8000)
cd frontend
npm install
npm run dev        # http://localhost:5173
npm test && npm run typecheck && npm run build
```

Secret scanning runs as a pre-commit hook (gitleaks): `pre-commit install` once after cloning.

### Reference data upkeep

- `backend/kairos/data/macro_calendar.json`: Fed meeting and CPI release dates. Update yearly from the [Fed calendar](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm) and the [BLS CPI schedule](https://www.bls.gov/schedule/news_release/cpi.htm). Last updated 2026-11-02; the 2027 Fed dates are marked tentative and should be re-checked.
- `backend/kairos/data/universe.txt`: S&P 500 tickers for Discover. Regenerate with `uv run python scripts/build_universe.py`.
- `backend/kairos/data/sector_pe.json`: median P/E per sector. Regenerate with `uv run python scripts/build_sector_pe.py` (takes a few minutes).

## License

[MIT](LICENSE)
