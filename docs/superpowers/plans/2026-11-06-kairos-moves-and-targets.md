# What Moved and Why + Clearer Analyst Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show, for each ticker, how unusual the last trading day's move was, how much was the
whole market, a sourced reason and what changed since the last reading, on the reading page and
a dashboard "Biggest moves" card. Also redesign the analyst targets card as sentences plus three boxes.

**Architecture:**
- Move context and "since last reading" changes are pure computations in `backend/kairos/analysis/`.
- They're stored on the Reading payload and surfaced through `/api/lists` summary fields.
- The move reason is one more optional `Claim` in the existing single Gemini structured-output request.
- The frontend adds pure helpers (`moves.ts`) and two cards, and rewrites the analyst card.

**Tech Stack:** Python 3.14, FastAPI, pydantic, pandas, pytest (asyncio auto) · React 19, TypeScript, Zod 4, Vitest + Testing Library.

**Spec:** `docs/superpowers/specs/2026-11-06-kairos-moves-and-targets-design.md`

## Global Constraints

- No extra Gemini requests. `move_reason` rides in the existing `summarize` call.
- The AI writes no numbers. Every %, ratio, date and count is computed in code.
- If articles don't explain a move, the UI says "No company-specific news found for this move." It never guesses.
- Share counts and portfolio values never appear in prompts (existing test `test_prompt_excludes_portfolio` must stay green).
- Notable move: `abs(change_pct) >= max(1.5 × typical_pct, 1.0)`, where `typical_pct` is the std of daily % changes over the last 30 completed sessions.
- Market baseline is VOO, fetched with `get_history("VOO")` and cached in memory for 3600 s.
- A row dated today in America/New_York while NY time is before 16:15 is an in-progress session. Exclude it from the move.
- All new Reading / ListEntry / AISummary fields are optional with `None` defaults. Old payloads must still parse, and the UI hides the new cards for them.
- Copy is plain language, never buy/sell wording. The analyst footer is exactly: "These are analysts' opinions, not a Kairos forecast. Analysts are often too optimistic."
- Backend checks: `uv run ruff format --check . && uv run ruff check . && uv run pytest -q`. Frontend checks: `npx tsc -b && npx oxlint && npx vitest run && npm run build`.
- Commits must have no AI attribution trailers.

## Review Focus

1. **Short history (new listing, < 32 completed closes):** no crash; `typical_pct=None`, `notable=False`. Pinned in Task 1.
2. **Zero or flat move:** `market_share` is `None`, with no division by zero. Pinned in Task 1.
3. **Stock and VOO last dates differ** (missing day or holiday mismatch): market fields omitted. Pinned in Task 1.
4. **Old saved readings** (no `move`/`changes`/`move_reason`): the API summary returns nulls and the UI hides the cards. Pinned in Tasks 5 and 7.
5. **Reason text changed between readings:** no verdict-change item. Mixed staleness on the dashboard: only latest-date rows plus a footnote. Pinned in Tasks 4 and 8.

---

### Task 1: Move context computation

**Files:**
- Modify: `backend/kairos/models.py` (add `Move`, add `move` to `Reading`)
- Create: `backend/kairos/analysis/move.py`
- Test: `backend/tests/analysis/test_move.py`

**Interfaces:**
- Produces:
  - in `models.py`:
    ```python
    class Move(BaseModel):
        date: date
        change_pct: float
        typical_pct: float | None
        notable: bool
        biggest_since: date | None = None      # only meaningful when notable; None = biggest in the history window
        market_open: bool = False              # an in-progress session was excluded
        market_change_pct: float | None = None
        market_notable: bool | None = None
        market_share: Literal["market", "half", "ticker", "opposite"] | None = None
    ```
    `Reading.move: Move | None = None`
  - in `analysis/move.py`:
    - `completed_closes(df: pd.DataFrame, now: datetime) -> pd.Series`
    - `compute_move(df: pd.DataFrame | None, now: datetime, market_df: pd.DataFrame | None = None, is_market: bool = False) -> Move | None`
    - constants: `NOTABLE_MULTIPLE = 1.5`, `NOTABLE_MIN_PCT = 1.0`, `TYPICAL_WINDOW = 30`, `MARKET_CLOSE_NY = time(16, 15)`, `SHARE_MARKET = 0.8`, `SHARE_HALF = 0.35`

- [ ] **Step 1: Write the failing tests** in `tests/analysis/test_move.py`. Add `series` to `tests/helpers.py` next to `make_df` (later tasks import it from there). `make_df(..., end=)` builds business-day indexes.

```python
# tests/helpers.py
def series(n=60, last=-9.3):
    """n-1 days alternating +0.5%/-0.5%, then a final move of `last` %."""
    closes, p = [100.0], 100.0
    for i in range(n - 2):
        p *= 1.005 if i % 2 == 0 else 0.995
        closes.append(p)
    closes.append(p * (1 + last / 100))
    return closes

# tests/analysis/test_move.py
AFTER_CLOSE = datetime(2026, 11, 6, 0, 0, tzinfo=UTC)   # Thu 19:00 NY, last row 2026-11-05 complete

def test_notable_drop_with_market_comparison():
    df = make_df(series(last=-9.3), end="2026-11-05")
    mkt = make_df(series(last=-4.4), end="2026-11-05")
    m = compute_move(df, AFTER_CLOSE, mkt)
    assert m.date == date(2026, 11, 5)
    assert m.change_pct == pytest.approx(-9.3, abs=0.01)
    assert 0.4 < m.typical_pct < 0.6
    assert m.notable is True
    assert m.biggest_since is None                       # nothing as big in the window
    assert m.market_change_pct == pytest.approx(-4.4, abs=0.01)
    assert m.market_share == "half"                       # 4.4/9.3 = 0.47
    assert m.market_notable is True

def test_normal_day_not_notable():
    m = compute_move(make_df(series(last=0.4), end="2026-11-05"), AFTER_CLOSE)
    assert m.notable is False and m.market_change_pct is None

def test_one_percent_floor_for_calm_tickers():
    closes = [100.0 + (0.01 if i % 2 else 0) for i in range(59)] + [100.9]   # typical ~0.01%
    assert compute_move(make_df(closes, end="2026-11-05"), AFTER_CLOSE).notable is False

def test_biggest_since_finds_last_larger_same_direction_move():
    closes = series(n=80, last=-9.3)
    closes[30] = closes[29] * 0.88                       # -12% earlier; later days rebased on it
    for i in range(31, 79): closes[i] = closes[i - 1] * (1.005 if i % 2 else 0.995)
    closes[79] = closes[78] * 0.907
    df = make_df(closes, end="2026-11-05")
    assert compute_move(df, AFTER_CLOSE).biggest_since == df.index[30].date()

def test_in_progress_session_excluded_during_us_hours():
    df = make_df(series(last=-3.0), end="2026-11-06")    # last row = Fri 2026-11-06
    during = datetime(2026, 11, 6, 15, 0, tzinfo=UTC)    # 10:00 NY
    m = compute_move(df, during)
    assert m.market_open is True and m.date == date(2026, 11, 5)
    after = datetime(2026, 11, 6, 22, 0, tzinfo=UTC)     # 17:00 NY
    assert compute_move(df, after).date == date(2026, 11, 6)

def test_market_share_bands_and_opposite():
    df = make_df(series(last=-5.0), end="2026-11-05")
    assert compute_move(df, AFTER_CLOSE, make_df(series(last=-4.5), end="2026-11-05")).market_share == "market"
    assert compute_move(df, AFTER_CLOSE, make_df(series(last=-1.0), end="2026-11-05")).market_share == "ticker"
    assert compute_move(df, AFTER_CLOSE, make_df(series(last=0.6), end="2026-11-05")).market_share == "opposite"

def test_market_ticker_itself_and_date_mismatch_omit_market():
    df = make_df(series(last=-4.4), end="2026-11-05")
    assert compute_move(df, AFTER_CLOSE, df, is_market=True).market_change_pct is None
    other = make_df(series(last=-4.4), end="2026-11-04")
    assert compute_move(df, AFTER_CLOSE, other).market_change_pct is None

def test_short_history_and_flat_move_are_safe():
    m = compute_move(make_df([100.0] * 10, end="2026-11-05"), AFTER_CLOSE)
    assert m.typical_pct is None and m.notable is False and m.market_share is None
    assert compute_move(make_df([100.0], end="2026-11-05"), AFTER_CLOSE) is None
    assert compute_move(None, AFTER_CLOSE) is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend && uv run pytest tests/analysis/test_move.py -q`
Expected: FAIL. `ImportError: cannot import name 'compute_move'`.

- [ ] **Step 3: Implement `Move` and `compute_move` in `kairos/analysis/move.py`**
- Fewer than 2 completed closes → `None`.
- `typical_pct` is the std of `pct_change() * 100` over the `TYPICAL_WINDOW` returns **before** the move day, so the move itself doesn't inflate "normal". It needs at least `TYPICAL_WINDOW + 2` closes, else `None`.
- `biggest_since`: walk returns backwards from the one before last. Take the first one with the same sign and `abs >= abs(change)`, and return its date. Compute it only when notable.
- The market comparison applies the same `completed_closes` to `market_df`. Use it only if its last date equals the stock's. `market_notable` uses the same notable rule on the market series.
- Share: if `change_pct == 0`, use `None`. Opposite signs → `"opposite"`. Otherwise use `ratio = market / change`: `>= SHARE_MARKET` → `"market"`, `>= SHARE_HALF` → `"half"`, else `"ticker"`.
- Normalize tz-aware indexes with `.date()` on each timestamp. yfinance indexes are America/New_York aware; `make_df` indexes are naive.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/analysis/test_move.py -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/kairos/models.py backend/kairos/analysis/move.py backend/tests/analysis/test_move.py
git commit -m "feat: move context (typical swing, biggest since, market share)"
```

### Task 2: Move on readings (VOO cache + build_reading)

**Files:**
- Create: `backend/kairos/services/market.py`
- Modify: `backend/kairos/services/readings.py` (`build_reading`, `_computed_for_prompt`)
- Modify: `backend/tests/services/fakes.py` (add `closes` knob), `backend/tests/conftest.py` (autouse cache clear)
- Test: `backend/tests/services/test_readings.py`

**Interfaces:**
- Consumes: `compute_move` (Task 1).
- Produces:
  - `MARKET_TICKER = "VOO"` and `MARKET_CACHE_SECONDS = 3600`;
  - `async def market_history(fetch: Callable[[str], Awaitable[tuple[pd.DataFrame | None, SourceStatus]]], now: datetime) -> pd.DataFrame | None`;
  - `clear_market_cache() -> None`;
  - `Reading.move` is populated by `build_reading`;
  - the prompt's computed data gains a `"move"` key: `move.model_dump()`, or `None`.

- [ ] **Step 1: Tests**
- In `fakes.py`, `Sources.__init__` gets `self.closes: dict[str, list[float]] = {}`.
- `get_history` returns `make_df(self.closes.get(t, [100.0] * 260), end="2026-10-30")` for tickers in `self.info` or in `self.closes`.
- Add to `test_readings.py`:

```python
from tests.helpers import series

async def test_reading_has_move_with_market(settings, conn, src):
    src.closes = {"NVDA": series(last=-9.3), "VOO": series(last=-4.4)}
    r = await build_reading(settings, conn, "NVDA", NOW)
    assert r.move.notable is True and r.move.market_share == "half"
    assert '"move"' in src.last_prompt

async def test_market_history_fetched_once_per_hour(settings, conn, src, monkeypatch):
    src.closes = {"VOO": series(last=-1.0)}
    calls = []
    async def counting(t, period="1y"):
        calls.append(t)
        return await src.get_history(t, period)
    monkeypatch.setattr(readings, "get_history", counting)
    await build_reading(settings, conn, "NVDA", NOW)
    await build_reading(settings, conn, "QQQ", NOW)
    assert calls.count("VOO") == 1

async def test_market_fetch_failure_omits_market_only(settings, conn, src):
    r = await build_reading(settings, conn, "NVDA", NOW)   # no VOO history in fakes
    assert r.move is not None and r.move.market_change_pct is None
```
Add a `conftest.py` autouse fixture that calls `clear_market_cache()` before each test.

- [ ] **Step 2: Run** `uv run pytest tests/services/test_readings.py -q`. Expected: the new tests FAIL (`AttributeError: 'Reading' ... move` or `None`).

- [ ] **Step 3: Implement**
- `market.py` holds a module-level `(fetched_at, df)` cache. A failed fetch is not cached.
- In `build_reading`:
  ```python
  market_df = None if symbol == MARKET_TICKER else await market_history(get_history, now)
  parts["move"] = compute_move(df, now, market_df, is_market=symbol == MARKET_TICKER)
  ```
  For VOO itself, pass its own `df` as `market_df` so that `market_notable` is still known (`is_market=True` blanks the other market fields).
- `_computed_for_prompt` adds `"move"`.

- [ ] **Step 4: Run** the full backend test suite. Expected: all pass.

- [ ] **Step 5: Commit** `feat: move context on readings with cached S&P 500 baseline`

### Task 3: AI move reason (same request)

**Files:**
- Modify: `backend/kairos/ai/schema.py`, `backend/kairos/ai/prompt.py`, `backend/kairos/ai/gemini.py`
- Modify: `backend/tests/services/fakes.py` (`move_reason` knob)
- Test: `backend/tests/ai/test_prompt.py`, `backend/tests/ai/test_gemini.py`

**Interfaces:**
- Produces: `AISummary.move_reason: Claim | None = None`, validated by the same `_valid` rule as `takeaway`.

- [ ] **Step 1: Tests**

```python
# test_prompt.py
def test_prompt_asks_for_move_reason_only_when_notable():
    p = build_prompt("NVDA", "NVIDIA", "stock", news, {"move": {"notable": True, "change_pct": -9.3}})
    assert "move_reason" in p and "only if move.notable is true" in p
# test_gemini.py: follow the existing fake-client pattern used for takeaway
async def test_move_reason_with_unknown_ids_is_dropped(...):  # parsed.move_reason source_ids=["zz"] → result.move_reason is None
async def test_valid_move_reason_kept(...):                    # source_ids=[valid id] → kept unchanged
```

- [ ] **Step 2: Run** `uv run pytest tests/ai -q`. Expected: FAIL.

- [ ] **Step 3: Implement**
- Add the field.
- Add this bullet to `INSTRUCTIONS`, verbatim:
  `- Write move_reason only if move.notable is true in the computed data: one plain sentence (max 25 words) on why the price moved on move.date, citing the ids of the articles that explain it. If the articles do not explain that move, or move.notable is false, leave move_reason empty (null).`
- In `summarize`'s `model_copy`, add `"move_reason": next(iter(_valid([parsed.move_reason], allowed_ids)), None) if parsed.move_reason else None`.
- In `fakes.Sources`, add `self.move_reason: Claim | None = None` and pass it into the returned `AISummary`.

- [ ] **Step 4: Run** the full backend suite. Expected: all pass.

- [ ] **Step 5: Commit** `feat: sourced move reason from the existing Gemini request`

### Task 4: "Since the last reading" changes

**Files:**
- Modify: `backend/kairos/models.py` (add `ChangeItem`, `Changes`, `Reading.changes`)
- Create: `backend/kairos/analysis/changes.py`
- Modify: `backend/kairos/services/readings.py` (fetch previous readings, compute before insert)
- Modify: `backend/tests/services/fakes.py` (`lean` knob, default `"bullish"`)
- Test: `backend/tests/analysis/test_changes.py`

**Interfaces:**
- Produces:
  - in `models.py`:
    ```python
    class ChangeItem(BaseModel):
        kind: Literal["lean", "verdict", "price_label", "hype", "target", "new_articles"]
        before: str | None = None   # lean/verdict/label values, "warning"/"clear", target as "327.14"
        after: str | None = None
        count: int | None = None    # new_articles only
        since: datetime             # the reading this item compares against
    class Changes(BaseModel):
        since: datetime             # immediately previous reading
        items: list[ChangeItem]
    ```
    `Reading.changes: Changes | None = None`
  - `compute_changes(current: Reading, previous: Reading | None, previous_ai: Reading | None) -> Changes | None` in `analysis/changes.py`
  - `TARGET_CHANGE_PCT = 5.0`
  - In `readings.py`: `previous` is the latest reading of the symbol, and `previous_ai` is the latest whose `ai_status = 'ok'`. Both are queried before the INSERT.

- [ ] **Step 1: Tests** in `tests/analysis/test_changes.py`. Build `base` with `build_reading(settings, conn, "NVDA", NOW)` (fakes `src` fixture), then derive variants with `model_copy(update=...)`.

```python
async def test_first_reading_has_no_changes(...):   # compute_changes(base, None, None) is None
async def test_lean_change_against_last_ok_ai_reading(...):
    # previous (1h ago) ai_status="budget_exhausted", previous_ai (2 days ago) lean bullish; current neutral
    ch = compute_changes(cur, prev, prev_ai)
    assert ch.since == prev.created_at
    lean = next(i for i in ch.items if i.kind == "lean")
    assert (lean.before, lean.after, lean.since) == ("bullish", "neutral", prev_ai.created_at)
async def test_verdict_change_only_when_same_reason_text(...):
    # same thesis_checked: supports→mixed gives item; different thesis_checked gives no verdict item
async def test_computed_changes_vs_immediately_previous(...):
    # price.label near_average→below_range; hype none→triggered ("clear"→"warning");
    # target_mean 327.14→310.0 (>5%) item with before "327.14"; 327→330 (<5%) no item;
    # sources: 2 ids new → new_articles count 2
async def test_no_items_returns_empty_list_not_none(...):  # identical readings → Changes(items=[])
```
Add an integration test in `test_readings.py`: build twice with `src.lean` changed from `"bullish"` to `"neutral"`. The second reading's `changes` has a lean item.

- [ ] **Step 2: Run.** Expected: FAIL (import error).
- [ ] **Step 3: Implement** `compute_changes` plus the readings wiring. Lean and verdict items are only produced when both readings have an `ai` with `ai_status == "ok"`.
- [ ] **Step 4: Run** the full backend suite. Expected: all pass.
- [ ] **Step 5: Commit** `feat: what changed since the last reading`

### Task 5: Move fields on list summaries

**Files:**
- Modify: `backend/kairos/api/routes.py` (`ListEntry`, `_summary`)
- Test: `backend/tests/api/test_lists_api.py`

**Interfaces:**
- Produces: these `ListEntry` fields, all optional `None`:
  - `move_date: str | None` (ISO);
  - `move_notable: bool | None`;
  - `move_change_pct: float | None`;
  - `move_typical_pct: float | None`;
  - `move_reason: str | None` (claim text; only when `ai_status == "ok"`);
  - `market_change_pct: float | None`;
  - `market_notable: bool | None`.

- [ ] **Step 1: Tests**
  - A list entry whose latest reading has a `move` and an `ai.move_reason` returns all seven fields.
  - An entry whose stored payload predates the feature (insert a payload JSON without `move`) returns them as `null`, and the request doesn't fail.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement** in `_summary`.
- [ ] **Step 4: Run** the full backend suite, ruff format/check. Expected: clean.
- [ ] **Step 5: Commit** `feat: move summary fields on list entries`

### Task 6: Frontend schemas + move helpers

**Files:**
- Modify: `frontend/src/api/schemas.ts`
- Create: `frontend/src/components/moves.ts`
- Test: `frontend/src/components/__tests__/moves.test.ts`

**Interfaces:**
- Produces:
  - Zod schemas:
    - `MoveSchema` (mirrors `Move`; dates as strings);
    - `ChangeItemSchema` and `ChangesSchema`;
    - `ReadingSchema.move` and `.changes` as `.nullable().optional()`;
    - `AISummarySchema.move_reason: ClaimSchema.nullable().optional()`;
    - the seven `ListEntrySchema` fields, each with `.nullable().default(null)`.
  - Types `Move`, `Changes`, `ChangeItem`.
  - In `moves.ts`:
    - `sinceWhen(moveDate: string, biggestSince: string | null | undefined): string | null`
    - `moveHeadline(move: Move, ticker: string): string`
    - `marketLine(move: Move): string | null`
    - `changeText(item: ChangeItem, headerSince: string): string`
    - `biggestMoves(entries: ListEntry[]): { date: string | null; marketChangePct: number | null; marketNotable: boolean; rows: ListEntry[]; skipped: number }`
    - `MAX_BIGGEST_MOVES = 5`

- [ ] **Step 1: Tests** (exact copy)

```ts
test('sinceWhen phrasing', () => {
  expect(sinceWhen('2026-11-05', '2026-04-01')).toBe('in 7 months')
  expect(sinceWhen('2026-11-05', '2026-10-15')).toBe('in 3 weeks')
  expect(sinceWhen('2026-11-05', '2026-10-29')).toBeNull()       // under 2 weeks
  expect(sinceWhen('2026-11-05', null)).toBe('in the past year')
})
test('moveHeadline', () => {
  expect(moveHeadline({ ...notableDrop, biggest_since: '2026-04-01' }, 'NVDA'))
    .toBe('Down 9.3% on Thu Nov 5 — its biggest one-day drop in 7 months.')
  expect(moveHeadline({ ...calmUp, change_pct: 0.4 }, 'NVDA')).toBe('Up 0.4% on Thu Nov 5 — a normal day for NVDA.')
})
test('marketLine bands', () => {
  expect(marketLine({ ...notableDrop, market_change_pct: -4.4, market_share: 'half' }))
    .toBe('The S&P 500 fell 4.4% the same day, so roughly half of the drop was the whole market.')
  // market → 'so most of the drop was the whole market.'; ticker → 'so most of the drop was specific to this ticker.'
  // opposite → 'The S&P 500 rose 0.6% the same day, so this drop went against the market.'
  // not notable or no market data → null
})
test('changeText', () => {
  // lean, same since as header: 'Lean: Bullish → Neutral'; different since: 'Lean: Bullish → Neutral (vs Nov 3)'
  // price_label: 'Add more?: now well below its recent range (was near average)'  (use PRICE_LABELS_SHORT text lowercased)
  // verdict: 'Your reason: Supports → Mixed'; hype: 'Hype warning signs appeared' / 'Hype warning signs cleared'
  // target: 'Average analyst target: $327 → $310'; new_articles: '14 new articles read' (1 → '1 new article read')
})
test('biggestMoves keeps only latest-date notable rows, ranked by unusualness', () => {
  // entries: A latest notable -5/typ 1 (5x), B latest notable -9/typ 3 (3x), C latest not notable, D stale notable, E no move
  const r = biggestMoves(entries)
  expect(r.rows.map((e) => e.ticker)).toEqual(['A', 'B'])
  expect(r.skipped).toBe(1)          // D only; E (never had a move) is not counted
  expect(r.date).toBe('2026-11-05')
})
```
Dates are formatted from the ISO date as UTC-free local parts (`new Date(y, m-1, d)`), weekday and month short names in `en-US`.

- [ ] **Step 2: Run** `npx vitest run src/components/__tests__/moves.test.ts`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npx vitest run && npx tsc -b`. Expected: pass.
- [ ] **Step 5: Commit** `feat: frontend move schemas and phrasing helpers`

### Task 7: "Why it moved" card on the reading

**Files:**
- Create: `frontend/src/components/reading/WhyItMovedCard.tsx`
- Modify: `frontend/src/components/ReadingPanel.tsx` (first child of `.rail-main`, before the chart), `frontend/src/index.css`
- Test: `frontend/src/components/__tests__/WhyItMovedCard.test.tsx`

**Interfaces:**
- Consumes: Task 6 helpers; the existing `Citations` component for source chips.
- Produces: `WhyItMovedCard({ reading }: { reading: Reading })`. It returns `null` when `reading.move` is missing.

- [ ] **Step 1: Tests**
  - **Notable move with a reason:** shows the headline, the market line, the reason text and a citation chip.
  - **Notable move, AI ok, no `move_reason`:** shows "No company-specific news found for this move."
  - **Notable move, `ai_status` not ok:** shows "AI read not available for this reading."
  - **Not notable:** shows the headline only.
  - **`market_open`:** shows "US market is open; this covers the last completed day."
  - **Changes:** header "Since the last reading (…)" plus item texts. Earnings line "Earnings in 11 days" when `events.next_earnings` is ≤ 14 days after `created_at`'s local date. Section hidden when there are no items and no earnings line.
  - **No `move`:** container empty.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Card title "Why it moved". The header time uses the same short date/time formatting as `VerdictCard`'s "updated" text.
- [ ] **Step 4: Run** the frontend checks. Expected: pass.
- [ ] **Step 5: Commit** `feat: why it moved card on readings`

### Task 8: Dashboard "Biggest moves"

**Files:**
- Create: `frontend/src/components/BiggestMovesCard.tsx`
- Modify: `frontend/src/components/Overview.tsx` (directly after the tiles section), `frontend/src/index.css`
- Test: `frontend/src/components/__tests__/Overview.test.tsx`

**Interfaces:**
- Consumes: `biggestMoves`, list entries from `useLists`, and `useSelection().select(ticker)` to open a reading.

- [ ] **Step 1: Tests** (through the msw lists handler)
  - **Notable movers:** rows show ticker, change % and reason. Clicking a row selects the ticker.
  - **Header:** "S&P 500 down 4.4% on Thu Nov 5". When `market_notable`, it adds " — a big day for the whole market".
  - **Row without a reason:** for a notable row whose `move_reason` is null, the text is "No company-specific news found". If `|market_change_pct| >= |move_change_pct| × 0.8` (same sign), it reads "About the same as the market; no company-specific news found".
  - **Footnote:** "1 ticker not refreshed for this day" when `skipped` is 1 ("2 tickers…" when plural).
  - **No notable rows:** "No unusual moves on the last trading day."
  - **No entry has a `move_date`:** card not rendered.
- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the frontend checks. Expected: pass.
- [ ] **Step 5: Commit** `feat: biggest moves on the dashboard`

### Task 9: Analyst targets card redesign

**Files:**
- Modify: `frontend/src/components/reading/AnalystTargetsCard.tsx`, `frontend/src/index.css` (remove the `.target-track`/`.target-mean`/`.target-now`/`.key-*` rules; add box styles)
- Test: `frontend/src/components/__tests__/AnalystTargetsCard.test.tsx` (rewrite)

**Interfaces:**
- Produces: `analystPosition(price: number, low: number, high: number): string`, exported from the card file. The component props are unchanged.

- [ ] **Step 1: Tests**

```tsx
test('sentence, three boxes, footer', () => {
  render(<AnalystTargetsCard quick={{ ...q, target_mean: 327.14, target_low: 180, target_high: 515, analyst_count: 58, analyst_rating: 'Strong buy' }} price={181.6} />)
  expect(screen.getByText('What analysts expect (12 months)')).toBeInTheDocument()
  expect(screen.getByText(/On average,/)).toHaveTextContent('On average, 58 analysts think NVDA will be around $327 in a year. Today it\'s $181.60.')
  expect(screen.getByText('$180')).toBeInTheDocument(); expect(screen.getByText('−1% from today')).toBeInTheDocument()
  expect(screen.getByText('$327')).toBeInTheDocument(); expect(screen.getByText('+80% from today')).toBeInTheDocument()
  expect(screen.getByText('$515')).toBeInTheDocument(); expect(screen.getByText('+184% from today')).toBeInTheDocument()
  expect(screen.getByText(/Average rating: Strong buy · These are analysts' opinions, not a Kairos forecast. Analysts are often too optimistic./)).toBeInTheDocument()
})
test('analystPosition order', () => {
  expect(analystPosition(600, 180, 515)).toBe("Today's price is above every analyst's target, so they think it's run ahead.")
  expect(analystPosition(176, 180, 515)).toBe("Today's price is below every analyst's target.")
  expect(analystPosition(181.6, 180, 515)).toBe("Today's price is right at the lowest guess — even the most cautious analyst expects about the same price.")
  expect(analystPosition(500, 180, 515)).toBe("Today's price is close to the highest guess.")
  expect(analystPosition(300, 180, 515)).toBe("Today's price is between the lowest and highest guesses.")
})
test('missing low/high shows sentence and average box only', () => { /* no 'Lowest'/'Highest' labels */ })
test('renders nothing without analyst coverage', () => { /* unchanged */ })
```
The ticker name in the sentence comes from a new optional prop, `ticker?: string`. `ReadingPanel` passes `reading.ticker`; when it's absent, the sentence says "the stock". Box prices are whole dollars, `$${Math.round(v)}`. Percentages are rounded to whole numbers with a sign; the minus sign is U+2212.

- [ ] **Step 2: Run.** Expected: FAIL.
- [ ] **Step 3: Implement.** Pass `ticker` from `ReadingPanel`.
- [ ] **Step 4: Run** the frontend checks. Expected: pass.
- [ ] **Step 5: Commit** `feat: analyst targets as plain sentences and three boxes`

### Task 10: End-to-end check and PR

- [ ] **Step 1:** Run the full backend and frontend checks (see Global Constraints). Expected: all green.
- [ ] **Step 2:** Run a live preview using the established safe pattern:
  - `docker build -t kairos:preview .`;
  - copy the DB from volume `kairos_kairos-data` via the SQLite backup API into the scratchpad;
  - `docker run` on `127.0.0.1:8001` with `SCHEDULER_ENABLED=false`, `BACKUP_DIR=`, and no env file.
  
  Refresh NVDA and VOO in the preview. No AI key in the preview, so expect "AI read not available". Screenshot:
  - the reading (Why it moved card, analyst card under the chart);
  - the dashboard (Biggest moves).
  
  Then remove the container, image and DB copy.
- [ ] **Step 3:** Run a final code review of the branch by a fresh reviewer subagent, and fix confirmed findings.
- [ ] **Step 4:** Push `feat/moves-and-targets` and open the PR, with no AI attribution in the body.
