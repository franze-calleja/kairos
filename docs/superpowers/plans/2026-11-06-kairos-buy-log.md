# Buy Log ("My buys") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the owner log buys and sells. Show positions with average cost, gains, "Your return" vs "Same $ in VOO", a buy history with what Kairos said that day, and use logged shares as the share count everywhere.

**Architecture:**
- New `trades` table plus a `services/trades.py` (storage, validation, net shares).
- Pure portfolio math in `services/portfolio.py`, fed by a new unadjusted-close adapter.
- New `/api/trades`, `/api/portfolio` and `/api/prices/{t}/close` routes. List entries and Exposure switch to effective shares.
- Frontend: a "My buys" view with a form and two tables, plus a read-only Exposure row for traded tickers.

**Tech Stack:** Python 3.14, FastAPI, pydantic, pandas, yfinance, SQLite, pytest (asyncio auto), respx not needed · React 19, TS, Zod 4, TanStack Query, Vitest + msw.

**Spec:** `docs/superpowers/specs/2026-11-06-kairos-buy-log-design.md`

## Global Constraints

- Trades, shares, costs and values are never put in any Gemini prompt.
- No new dependencies and no `.env` changes. All data is local SQLite.
- `trade_date` is the **US trading date (New York)**. It must be ≤ today in America/New_York and ≥ 2000-01-01.
- Closes use yfinance `auto_adjust=False`: split-adjusted, not dividend-adjusted. A non-trading date uses the last close on or before it. If the date is today in NY and NY time is before 16:15, use the latest price.
- **Average cost method.** A sell removes `shares × avg_cost` from the cost basis. Realized gain is `shares × (price − avg_cost)`.
- **Your return** = `(value_now + sell_proceeds − total_bought) / total_bought × 100`.
- **Same $ in VOO**:
  - each buy puts the same $ into VOO at VOO's close on that date;
  - each sell sells the same fraction of the shadow position;
  - its % uses the same formula as Your return;
  - it is `None` for VOO itself;
  - the totals row includes fully sold tickers.
- **Sell cap:** a sell up to `SHARE_EPSILON = 0.0001` over the held amount is capped to the held amount. A position below `SHARE_EPSILON` counts as closed.
- "What Kairos said" is the latest reading created before 16:00 NY on the trade date, and at most 36 h before that moment.
- **Copy (exact):**
  - empty state help: "Already own some? Log it as one buy at your average price (Gotrade shows it on the position)."
  - date hint: "Bought after midnight your time? Use the previous day (US date)."
  - Exposure read-only text: "from My buys".
- No browser dialogs: delete confirmation is inline ("Delete? Yes / No").
- Backend checks: `cd backend && uv run ruff format --check . && uv run ruff check . && uv run pytest -q`. Frontend checks: `cd frontend && npx tsc -b && npx oxlint && npx vitest run && npm run build`.
- Commits carry no AI attribution.

## Review Focus

1. **Weekend/holiday date, or a date before the ticker's first close:** the weekend uses the prior close; a date with no close at all → 422 "No price for TICKER on DATE". Pinned in Task 2.
2. **Deleting a buy that a later sell depends on:** 422 with a message, and nothing deleted. Pinned in Task 1.
3. **Removing a holding that has trades:** the trades stay and still show on My buys. Exposure ignores the ticker until it's re-added. Pinned in Tasks 4–5.
4. **VOO as a traded ticker:** its VOO column is `None`, and its buys still count in the totals' shadow. Pinned in Task 3.
5. **Yahoo outage while building the portfolio:** `value`/`gain` are `None` for tickers without a price, and the VOO fields are `None` without VOO closes. No 500. Pinned in Task 4.

---

### Task 1: Trades storage and validation

**Files:**
- Modify: `backend/kairos/db.py` (add `trades` table to `SCHEMA`)
- Create: `backend/kairos/services/trades.py`
- Test: `backend/tests/services/test_trades.py`

**Interfaces:**
- Produces:
  - Table: `trades (id INTEGER PRIMARY KEY AUTOINCREMENT, ticker TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('buy','sell')), trade_date TEXT NOT NULL, shares REAL NOT NULL CHECK (shares > 0), price REAL NOT NULL CHECK (price > 0), created_at TEXT NOT NULL)`, plus `CREATE INDEX IF NOT EXISTS idx_trades_ticker ON trades (ticker, trade_date, id)`.
  - In `kairos/services/trades.py`:
    ```python
    SHARE_EPSILON = 0.0001
    MIN_DATE = date(2000, 1, 1)
    class TradeError(ValueError): ...
    class Trade(BaseModel): id: int; ticker: str; side: Literal["buy","sell"]; trade_date: date; shares: float; price: float; created_at: datetime
    def ny_today(now: datetime) -> date
    def list_trades(conn, ticker: str | None = None) -> list[Trade]           # newest first (trade_date desc, id desc)
    def held_shares(trades: list[Trade]) -> float                               # replay in (trade_date, id) order; < SHARE_EPSILON → 0.0
    def add_trade(conn, ticker: str, side: str, trade_date: date, price: float, now: datetime, shares: float | None = None, amount: float | None = None) -> Trade
    def delete_trade(conn, trade_id: int) -> None                               # KeyError if missing
    def net_shares(conn, ticker: str) -> float | None                           # None when the ticker has no trades
    ```

- [ ] **Step 1: Tests** (`conn` fixture; `NOW = datetime(2026, 11, 6, 20, 0, tzinfo=UTC)`, which is 15:00 NY Fri Nov 6)

```python
def test_buy_by_amount_computes_shares():
    t = add_trade(conn, "nvda", "buy", date(2026, 11, 5), price=181.6, now=NOW, amount=25.0)
    assert t.ticker == "NVDA" and t.shares == pytest.approx(25 / 181.6)
def test_exactly_one_of_shares_or_amount(): # both or neither → TradeError("Give shares or a $ amount, not both")
def test_rejects_future_and_ancient_dates_and_bad_numbers():
    # date(2026, 11, 7) → TradeError ("in the future"); date(1999, 12, 31) → TradeError; price 0 / shares -1 → TradeError
def test_sell_cannot_exceed_holdings_on_that_date():
    # buy 1.0 on 11-03; sell 0.5 on 11-02 → TradeError ("You only held 0 NVDA on 2026-11-02")
def test_sell_within_epsilon_is_capped_and_closes_position():
    # buy amount=25 @181.6 on 11-03; sell shares=round(25/181.6, 4)+0.00004 on 11-05 → stored shares == buy shares; net_shares == 0.0
def test_delete_buy_that_a_later_sell_needs_is_rejected():
    # buy 1 (11-02), sell 1 (11-04); delete_trade(buy.id) → TradeError; both rows still present
def test_net_shares_none_without_trades_and_list_order():
    # net_shares("VOO") is None; list_trades returns newest first
```

- [ ] **Step 2: Run** `cd backend && uv run pytest tests/services/test_trades.py -q`. Expected: FAIL (ImportError).
- [ ] **Step 3: Implement.**
  - `ny_today` = `now.astimezone(ZoneInfo("America/New_York")).date()`.
  - Normalize tickers with `normalize_ticker`. Message wording follows the tests.
  - Validation for add and delete replays the candidate trade list in `(trade_date, id)` order. A running balance below `−SHARE_EPSILON` is an error.
  - A sell within epsilon over the held amount is capped at add time.
- [ ] **Step 4: Run** the full backend suite. Expected: green.
- [ ] **Step 5: Commit** `feat: trades storage with sell and date validation`

### Task 2: Close on a date (adapter and endpoint)

**Files:**
- Modify: `backend/kairos/adapters/prices.py` (add `get_closes`)
- Create: `backend/kairos/services/closes.py`
- Modify: `backend/kairos/api/routes.py` (add `GET /prices/{ticker}/close`)
- Test: `backend/tests/services/test_closes.py`, `backend/tests/api/test_trades_api.py` (create)

**Interfaces:**
- Produces:
  - `async def get_closes(ticker: str, start: date) -> tuple[pd.Series | None, SourceStatus]`. Uses `yf.Ticker(t).history(start=start - 7 days, auto_adjust=False)["Close"]`, indexed by `date`.
  - In `services/closes.py`:
    - `CLOSES_CACHE_SECONDS = 3600`
    - `async def closes_since(ticker: str, start: date, now: datetime) -> pd.Series | None`: cached per `(ticker)`. The cache entry is reused when its start ≤ requested start and it's younger than 1 h.
    - `def close_on(series: pd.Series, day: date) -> tuple[date, float] | None`: last close on or before `day`.
    - `async def close_for(ticker: str, day: date, now: datetime) -> tuple[date, float] | None`: if `day` is NY-today and NY time is before 16:15, use `get_info` `regularMarketPrice` (fallback `previousClose`) dated today. Otherwise use `close_on(closes_since(...))`.
    - `clear_closes_cache()`
  - Route: `GET /api/prices/{ticker}/close?date=YYYY-MM-DD` → `{"date": "...", "close": float}`. Unknown ticker or no close → 422 `"No price for {T} on {date}"`.

- [ ] **Step 1: Tests**
  - **`close_on` weekend:** Sat 2026-11-07 → the Fri 11-06 close.
  - **`close_on` before the first close:** returns `None`.
  - **`close_for` during market hours:** NY-today at 10:00 NY uses the info price, dated today.
  - **`close_for` after close:** NY-today at 17:00 NY uses that day's close.
  - **Cache:** two calls fetch once (monkeypatch `get_closes` with a counter; autouse `clear_closes_cache` in conftest).
  - **API:** 200 shape. A date before history → 422 with the message.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full backend suite. Expected: green.
- [ ] **Step 5: Commit** `feat: unadjusted close lookup for a trade date`

### Task 3: Portfolio math (pure)

**Files:**
- Create: `backend/kairos/services/portfolio.py` (pure functions only in this task)
- Test: `backend/tests/services/test_portfolio_math.py`

**Interfaces:**
- Consumes: `Trade` (Task 1), `close_on` (Task 2).
- Produces:
  ```python
  class Position(BaseModel):
      ticker: str; shares: float; avg_cost: float | None; invested: float
      value: float | None; gain: float | None; gain_pct: float | None
      realized: float; total_bought: float; sell_proceeds: float
      return_pct: float | None; voo_pct: float | None
  def position_for(ticker: str, trades: list[Trade], price_now: float | None,
                   voo_closes: pd.Series | None, voo_now: float | None) -> Position
  def totals(positions: list[Position]) -> dict   # invested, value, gain, return_pct, voo_pct over ALL positions incl. closed
  ```
  The `voo_pct` aggregate in `totals` uses each position's shadow figures, so `Position` also carries `voo_value: float | None` and `voo_proceeds: float | None`.

- [ ] **Step 1: Tests** (exact numbers)

```python
def test_average_cost_and_unrealized_gain():
    # buy 1 @100 (11-02), buy 1 @200 (11-03); price_now 180
    p = position_for("NVDA", trades, 180, None, None)
    assert (p.shares, p.avg_cost, p.invested, p.value, p.gain) == (2, 150, 300, 360, 60)
    assert p.gain_pct == pytest.approx(20.0) and p.return_pct == pytest.approx(20.0)
def test_sell_realizes_at_average_cost():
    # + sell 1 @240 (11-04): realized 90, invested 150, shares 1, sell_proceeds 240, total_bought 300
    # value 180 → return_pct = (180 + 240 - 300) / 300 * 100 = 40.0 ; gain = 30, gain_pct = 20.0
def test_same_dollars_in_voo_shadow():
    # buys $100 on 11-02 and $200 on 11-03; VOO closes 11-02=500, 11-03=400 → shadow 0.2 + 0.5 = 0.7 VOO
    # voo_now 450 → voo_value 315 → voo_pct = (315 - 300)/300*100 = 5.0
    # then sell half the real position on 11-04 → shadow sells half (0.35 VOO @ VOO close 11-04=420 → proceeds 147)
def test_voo_itself_has_no_voo_pct_and_missing_data_is_none():
    # ticker "VOO" → voo_pct None; price_now None → value/gain/return_pct None; voo_closes None → voo_pct None
def test_totals_include_closed_positions():
    # one open (return 20%) + one fully sold position → totals['return_pct'] over both; closed counted in invested=0
```

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Replay in `(trade_date, id)` order. A buy's dollar amount is `shares × price`.
- [ ] **Step 4: Run** the full backend suite. Expected: green.
- [ ] **Step 5: Commit** `feat: average-cost positions and same-dollars-in-VOO comparison`

### Task 4: Trades and portfolio API (+ what Kairos said)

**Files:**
- Modify: `backend/kairos/services/portfolio.py` (add `kairos_said`, `build_portfolio`)
- Modify: `backend/kairos/api/routes.py`
- Test: `backend/tests/api/test_trades_api.py`, `backend/tests/services/test_portfolio.py`, `backend/tests/services/test_readings.py` (privacy)

**Interfaces:**
- Consumes: Tasks 1–3, `services/exposure._position`-style current price. Reuse the latest-reading price when it's younger than the exposure `PRICE_MAX_AGE`, else `get_info`. Extract a shared `current_price(conn, ticker, now) -> float | None` into `services/exposure.py` and use it from both places.
- Produces:
  - `def kairos_said(conn, ticker: str, trade_date: date) -> dict | None`. Returns `{"price_label": str | None, "lean": str | None, "ai_status": str}` for the latest reading with `created_at < trade_date 16:00 America/New_York` and `≥ that − 36h`, else `None`.
  - `async def build_portfolio(conn, now) -> dict` returns:
    - `{"positions": [Position…open only], "totals": {...}, "realized_closed": float, "history": [...]}`;
    - each history row is `{id, ticker, side, trade_date, shares, price, amount, kairos_said, since_pct, voo_since_pct}`, and buys only get `since_pct`/`voo_since_pct`.
  - Routes:
    - `GET /api/trades` → `list[Trade]`.
    - `POST /api/trades` with body `TradeIn {ticker, side, date, shares?, amount?, price}` → 201 `Trade`. The ticker is checked like `post_list` (unknown → 422). It's added to holdings via `add_ticker(conn, "holdings", …)`. A `TradeError` → 422.
    - `DELETE /api/trades/{id}` → 204. Missing → 404; `TradeError` → 422.
    - `GET /api/portfolio`.

- [ ] **Step 1: Tests**
  - **`kairos_said` window:** a reading at 2026-11-06T13:00Z (21:00 Manila Nov 6) counts for trade date 11-06 (before 21:00Z = 16:00 NY). A reading at 2026-11-06T22:00Z doesn't. A reading 40 h earlier doesn't.
  - **API round trip:** POST a buy with an amount → it appears in GET `/api/trades` and in `/api/portfolio` positions. The ticker was added to holdings.
  - **DELETE:** 204; then 404 for the same id.
  - **Bad sell:** 422 with the message.
  - **Unknown ticker:** 422.
  - **Removing the holding:** the trade still shows in `/api/portfolio` history and positions.
  - **Yahoo down:** monkeypatch the price and closes helpers to return `None` → `/api/portfolio` is 200 with `value` null and `voo_pct` null.
  - **Privacy** (in `test_readings.py`): after logging a trade, `src.last_prompt` contains neither the share count nor the price string.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full backend suite. Expected: green.
- [ ] **Step 5: Commit** `feat: trades and portfolio API with what Kairos said that day`

### Task 5: Effective shares in list entries and Exposure

**Files:**
- Modify: `backend/kairos/api/routes.py` (`ListEntry.shares_source`, `_entry`)
- Modify: `backend/kairos/services/exposure.py` (`compute_exposure`)
- Test: `backend/tests/api/test_lists_api.py`, `backend/tests/api/test_exposure_api.py`

**Interfaces:**
- Consumes: `net_shares` (Task 1).
- Produces:
  - `ListEntry.shares_source: Literal["trades", "manual"] | None`.
  - For holdings with trades: `shares = net_shares` (0.0 when closed) and `shares_source="trades"`. With only a manual count: `"manual"`. Neither: `None`.
  - `compute_exposure` iterates the holdings list. It uses `net_shares` when not `None` and skips tickers with 0 shares; otherwise it uses the manual shares, as today.

- [ ] **Step 1: Tests**
  - **List entry:** a holding with a manual 5 shares plus a logged buy of 2 → `shares == 2`, `shares_source == "trades"`. A manual-only holding → `"manual"`.
  - **Exposure:** a position with trades uses the net shares. After a full sell it's absent.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the full backend suite and ruff. Expected: green.
- [ ] **Step 5: Commit** `feat: logged trades drive share counts in lists and exposure`

### Task 6: Frontend data layer + My buys view shell

**Files:**
- Modify: `frontend/src/api/schemas.ts`, `frontend/src/api/hooks.ts`, `frontend/src/store/selection.ts` (`View` adds `'buys'`), `frontend/src/App.tsx`, `frontend/src/components/TopBar.tsx` ("My buys" button before "Exposure")
- Create: `frontend/src/components/BuysPage.tsx` (empty state only in this task)
- Test: `frontend/src/components/__tests__/BuysPage.test.tsx`, `frontend/src/components/__tests__/TopBar.test.tsx`

**Interfaces:**
- Produces:
  - Zod schemas:
    - `TradeSchema`;
    - `PositionSchema`;
    - `PortfolioSchema` with `positions`, `totals {invested, value, gain, return_pct, voo_pct}`, `realized_closed`, `history[]` (`kairos_said` nullable object);
    - `CloseSchema {date, close}`;
    - `ListEntrySchema.shares_source: z.enum(['trades','manual']).nullable().default(null)`.
  - Hooks:
    - `usePortfolio()` (key `['portfolio']`);
    - `useClose(ticker: string | null, date: string | null)` (key `['close', ticker, date]`, enabled when both are set, `retry: false`);
    - `useAddTrade()` and `useDeleteTrade()`. Both invalidate `['portfolio']`, `['lists']` and `['exposure']`.
- [ ] **Step 1: Tests**
  - **TopBar:** "My buys" sets the view to `'buys'`.
  - **BuysPage, empty portfolio:** shows the help copy exactly, plus one line: "Log your buys to see your average cost, gains and how they compare with simply buying VOO."
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Add an msw handler default for `/api/portfolio` with an empty portfolio in `src/test/handlers.ts`.
- [ ] **Step 4: Run** the frontend checks. Expected: green.
- [ ] **Step 5: Commit** `feat: my buys view, data hooks and nav`

### Task 7: Add-a-buy form

**Files:**
- Create: `frontend/src/components/AddTradeForm.tsx`
- Modify: `frontend/src/components/BuysPage.tsx`, `frontend/src/index.css`
- Test: `frontend/src/components/__tests__/AddTradeForm.test.tsx`

**Interfaces:**
- Consumes: `useClose`, `useAddTrade`, `usePortfolio` (for held shares when selling), `normalizeTicker`.
- Produces: `AddTradeForm()`.

- [ ] **Step 1: Tests** (msw)
  - **Price pre-fill:** typing a ticker with the default date fetches the close and fills the price. It shows "(close on Fri Nov 6)".
  - **Share preview:** an amount of 25 at price 181.60 shows "= 0.1377 shares".
  - **Save:** POST body `{ticker:'NVDA', side:'buy', date, amount:25, price:181.6}`. Afterwards the ticker and date are kept and the amount is cleared.
  - **Shares mode:** sends `shares`.
  - **Sell all:** with Sell selected, "Sell all" fills the held shares from the portfolio position. A server 422 message is shown.
  - **Date:** the input defaults to today's New York date and carries the US-date hint copy.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Get today's NY date with `Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' })`. Editing the price disables auto-fill until the ticker or date changes.
- [ ] **Step 4: Run** the frontend checks. Expected: green.
- [ ] **Step 5: Commit** `feat: add a buy or sell with that day's close pre-filled`

### Task 8: Positions and history tables

**Files:**
- Modify: `frontend/src/components/BuysPage.tsx`, `frontend/src/index.css`
- Test: `frontend/src/components/__tests__/BuysPage.test.tsx`

**Interfaces:**
- Consumes: `usePortfolio`, `useDeleteTrade`, `PRICE_LABELS_SHORT`, `LeanPill` (or a plain pill), `pct`/`money` helpers.

- [ ] **Step 1: Tests**
  - **Positions:** headers are exactly Ticker, Shares, Avg cost, Invested, Value now, Gain, Your return, Same $ in VOO. Shares show 4 decimals. Gain shows "+$12.44 (+6.1%)". A `null` VOO % shows "—".
  - **Totals:** a totals row, plus "Realized from sales: +$X" when `realized_closed` ≠ 0.
  - **History:** date, ticker, Buy/Sell, amount, price, the Kairos-said pills (or "no reading that day"), and since "−13.6% (VOO −2.9%)".
  - **Delete:** clicking Delete shows "Delete? Yes / No"; Yes calls DELETE. A 422 message is shown inline.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the frontend checks. Expected: green.
- [ ] **Step 5: Commit** `feat: positions and buy history tables`

### Task 9: Exposure read-only rows

**Files:**
- Modify: `frontend/src/components/ExposurePage.tsx`
- Test: `frontend/src/components/__tests__/ExposurePage.test.tsx`

- [ ] **Step 1: Test:** a holding with `shares_source: 'trades'` and shares 0.3268 shows "0.3268 · from My buys" (link or button to the buys view) and no input. A `'manual'` holding still shows the input.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the frontend checks. Expected: green.
- [ ] **Step 5: Commit** `feat: exposure shows logged shares read-only`

### Task 10: End-to-end check and PR

- [ ] **Step 1:** Run the full backend and frontend checks.
- [ ] **Step 2:** Live preview using the established safe pattern: build `kairos:preview`; copy the DB from `kairos_kairos-data` via the SQLite backup API into the scratchpad; `docker run` on `127.0.0.1:8001` with `SCHEDULER_ENABLED=false`, `BACKUP_DIR=` and no env file.
  - Log 2 buys and 1 sell through the API on the copy.
  - Screenshot My buys and Exposure.
  - Remove the container, image and DB copy.
- [ ] **Step 3:** Final whole-branch review by a fresh reviewer (most capable model). Fix confirmed Critical/Important findings with RED→GREEN tests.
- [ ] **Step 4:** If PR #8 has merged, rebase this **unpushed** branch onto `main` and re-run the checks. Then push `feat/buy-log` and open the PR, with no AI attribution.
