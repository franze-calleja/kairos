# Kairos — Buy log ("My buys")

Date: 2026-11-06 · Status: approved in chat (mockup `.superpowers/brainstorm/*/content/buy-log.html`)

## Intent

The owner buys small, fractional amounts on Gotrade (VOO, QQQ, NVDA and ideas from TikTok/Reddit)
and wants a second opinion over time, not just per reading. Today Kairos only knows a manually typed
share count per holding. A buy log lets the owner record each purchase once and then see:

- average cost, total invested, value now and gain/loss per position;
- whether those exact buys beat simply buying the S&P 500 (VOO) on the same days;
- for each buy, **what Kairos said that day** and how it has done since, so after a few months the
  owner can judge whether Kairos's readings helped their timing (complements the track record).

## Goals

1. Record buys and sells: ticker, date, **$ amount or share count**, price (pre-filled with that
   day's close, editable).
2. "Your positions" table: shares, average cost, invested, value now, gain $ and %, and "Same $ in
   VOO" %.
3. "Buy history" table: date, ticker, amount, price, what Kairos said that day (Add more? label +
   lean), change since vs VOO over the same period. Delete an entry.
4. Logged trades become the source of share counts for Exposure and the dashboard, so the owner
   enters things once.

## Non-goals

- No import from Gotrade or any broker (export format unverified); entry is manual.
- No fees, taxes, dividends or currency conversion (all USD, price-only returns).
- No automatic stock-split adjustment of logged shares (rare for these holdings; the owner can
  delete and re-log). Called out in the UI help text.
- No editing an entry in place (delete and re-add) in v1.
- No new dashboard tiles; the existing portfolio value simply uses the new share counts.

## Anti-goals

- **Portfolio data reaching the AI.** Trades, share counts, costs and values are never put in any
  Gemini prompt (extends the existing rule and its test).
- **Advice.** No "you should buy/sell", no tax guidance. Numbers and comparisons only.
- **Sending data anywhere.** Everything stays in the local SQLite database (covered by the existing
  daily backups).

## Decided (by the owner, from the mockup)

- A new top-bar page "My buys" with three parts: Add a buy, Your positions, Buy history.
- Buy/Sell switch on the same form; $ amount or shares switch; price pre-filled with that day's
  close and editable.
- "Same $ in VOO" column and "what Kairos said that day" in the history.
- Shares from the buy log feed Exposure and the dashboard.

## Design

### Data

New table `trades`:
`id INTEGER PK, ticker TEXT, side TEXT CHECK (buy|sell), trade_date TEXT (YYYY-MM-DD),
shares REAL > 0, price REAL > 0, created_at TEXT`.
Shares are stored; when the owner enters a $ amount the server computes
`shares = amount / price` (kept at full float precision; UI shows 4 decimals).

### Share counts: one source of truth *(designer call)*

- A holding with **at least one logged trade** uses `sum(buy shares) − sum(sell shares)` as its
  share count everywhere (Exposure, dashboard, list entries). Its manual share count is ignored and
  the Exposure input for it becomes read-only text "from My buys".
- A holding with **no logged trades** keeps today's manual share count behaviour unchanged.
- Help text on the page: "Already own some? Log it as one buy at your average price (Gotrade shows
  it on the position)." This replaces any "starting position" concept.
- Logging a buy for a ticker not in My holdings adds it to My holdings. Selling everything leaves
  the ticker in the list (the owner can remove it).

### Trade date = the US market day *(designer call)*

`trade_date` is the **US trading date** (New York), because closes, the VOO comparison and "since"
figures are per US session. The form labels it "US trade date", defaults to today's date in New
York, and hints: "Bought after midnight your time? Use the previous day (US date)."

### Removing a holding that has trades *(designer call)*

Trades are kept. The position still appears on My buys; Exposure and the dashboard stay driven by
the My holdings list, exactly as today, so it drops out of those until the ticker is re-added (and
then its logged shares count again). Nothing is deleted implicitly.

### Selling everything *(designer call)*

The Sell form has a "Sell all" link that fills the exact held share count. A sell up to 0.0001
shares above the held amount is capped to the held amount (display rounding), and a position under
0.0001 shares counts as closed (hidden from the positions table, shares 0 everywhere).

### Validation

- Ticker must exist (same check as adding to a list); normalized like elsewhere.
- `trade_date` not after today's New York date and not before 2000-01-01.
- Exactly one of `shares` / `amount` given, > 0; `price` > 0.
- A sell may not exceed the shares held on that date (trades replayed in date order, then id).
  Deleting a buy that would make a later sell exceed holdings is rejected with a clear message.
- Errors are 422 with a plain message the form shows.

### Price for a date

`GET /api/prices/{ticker}/close?date=YYYY-MM-DD` → `{ "date": "<date used>", "close": <float> }`.
Uses yfinance closes with `auto_adjust=False`: **not dividend-adjusted, but split-adjusted**
*(designer call: true pre-split prices would need reversing split history; split-adjusted prices
match today's share counts, and splits after a logged buy are a non-goal)*. If the date is not a
trading day, use the last close on or before it. If the date is today in New York and the market
hasn't closed (before 16:15 NY), return the latest price. The same close series is used for the
VOO shadow position. The form shows "(close on Fri Nov 6)" next to the price.

### Calculations (all in code, price-only)

- **Average cost** method. Buys raise cost basis; a sell removes `shares × avg cost` from the basis
  and records realized gain `shares × (sell price − avg cost)`.
- Position: `shares`, `avg_cost`, `invested` (= remaining cost basis), `value` (= shares × current
  price, current price from the latest reading or Yahoo like Exposure does), `gain` and `gain_pct`
  (vs invested), `realized` (sum of realized gains).
- **Your return** (per ticker and total): `(value now + sell proceeds − total bought $) / total
  bought $`, i.e. total return including sales. *(Designer call)* This, not the unrealized Gain %,
  is the number shown next to "Same $ in VOO", so the comparison is like-for-like after sells.
- **Same $ in VOO**: replay the ticker's trades into a shadow VOO position. Each buy puts the same
  dollar amount into VOO at VOO's unadjusted close on that date. Each sell sells the same
  *fraction* of the shadow position as of the real one. Report
  `voo_pct = (shadow value now + shadow sell proceeds − total bought $) / total bought $`, next to
  the real `(value now + sell proceeds − total bought $) / total bought $`. For VOO itself the
  column shows "—". The totals row does the same across all tickers, **including fully sold
  ones** hidden from the table.
- **Buy history "since"** (buys only): `% change from the buy price to now`, and VOO's % change
  from its close on the buy date to now.
- Positions with 0 shares are hidden from the positions table; their realized gain still counts in
  a "Realized from sales" line under the table.

### "What Kairos said that day" *(designer call)*

The most recent saved reading for that ticker created **before 16:00 New York time on the trade
date** (the session close) and **no more than 36 hours earlier**. With readings at 07:00 and 21:00
Manila, this picks the reading the owner could have seen before or during that US session. Show its Add more? label (short form) and lean pill; otherwise
"no reading that day". Read from stored payloads only; no new fetches.

### API

- `GET /api/trades` → list, newest first.
- `POST /api/trades` `{ticker, side, date, shares | amount, price}` → 201 with the created trade.
- `DELETE /api/trades/{id}` → 204 (422 if it would break a later sell).
- `GET /api/portfolio` → `{positions: [...], totals: {...}, realized_closed: float,
  history: [...]}` with the fields above.
- `GET /api/prices/{ticker}/close?date=`.
- List entries' `shares` reflects the effective share count; add `shares_source: "trades" |
  "manual" | null`.

### UI

- Top bar button "My buys" (view `buys`), placed before "Exposure".
- **Add a buy** form as in the mockup: Buy/Sell switch, ticker, date (default today), $ amount /
  Shares switch, amount input, price input pre-filled from the close endpoint when ticker + date are
  set (editable), live "= 0.1377 shares" preview, Save. After saving, the tables refresh and the
  form keeps ticker/date for quick repeat entry.
- **Your positions** table: Ticker, Shares, Avg cost, Invested, Value now, Gain ($ and % on the
  remaining position), Your return, Same $ in VOO; totals row; "Realized from sales" line.
- **Buy history** table as in the mockup, using existing table styles.
  Delete in history uses an inline "Delete? Yes / No" (no browser dialogs).
- Empty state: one line explaining what logging buys gives you, plus the help text above.
- Exposure: read-only "from My buys" for tickers with trades.

## Constraints

- Existing stack and patterns (FastAPI routes + services, pydantic, SQLite migrations via
  `CREATE TABLE IF NOT EXISTS`; React + TanStack Query + Zod).
- TDD; backend + frontend checks green; existing privacy test extended to trades.
- No new dependencies; no `.env` changes.

## Left to the builder

- Module/file names, exact pydantic models, query structure, caching of historical closes (VOO
  closes for many dates should be one history fetch, not one per trade).
- Table styling and the exact empty-state wording within the rules above.
