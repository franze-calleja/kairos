# Kairos — "What moved and why" + clearer analyst targets

Date: 2026-11-06 · Status: approved in chat (mockups in `.superpowers/brainstorm/`, screens
`moves-and-why.html` and `analyst-targets-v2.html`)

## Intent

When the owner opens Kairos after a refresh, the first thing they look for is **the moves, and
why something dropped or went up**. Today a reading shows a day change number and an AI lean, but
nothing says "this was a big move for this ticker", how much of it was the whole market, or what
changed since the last reading. Separately, the analyst targets card (shipped in PR #6) uses a
range strip with a colour legend that the owner found hard to read.

This work makes both instantly readable, without extra AI requests and without Kairos itself
predicting prices.

## Goals

1. **Dashboard: "Biggest moves".** A card on the home page listing holdings + watchlist tickers
   whose last trading day move was unusual for that ticker, each with a one-line reason.
2. **Reading: "Why it moved".** At the top of each reading: size of the last trading day move with
   context, how much of it was the market, and a sourced reason.
3. **Reading: "Since the last reading".** A short list of what changed versus the previous reading
   of the same ticker.
4. **Analyst targets card redesign** (owner chose "A + B combined"): plain sentences plus three
   boxes (Lowest / Average / Highest, each with % from today).

## Non-goals

- No new data sources, no intraday data, no push notifications (Discord/email remain later).
- No change to how the lean is produced or to the track record.
- The buy log (owner's feature 2) is a separate, later design.

## Anti-goals (would make this a failure even if it works)

- **Kairos inventing explanations.** If the articles don't explain a move, say so ("no
  company-specific news found"); never guess.
- **AI-generated numbers.** All percentages, ratios, dates and counts are computed in code. The AI
  only writes the reason sentence, citing article ids like every other claim.
- **Extra Gemini requests.** The reason comes from the same single request that already builds the
  reading (free tier budget is tight: the owner runs 5 rpm).
- **Buy/sell language** or anything that reads as a Kairos price forecast.
- **Portfolio data reaching the AI.** Share counts/values are never in prompts (unchanged rule).

## Decided (by the owner, from the mockups)

- Two places for moves: a dashboard "Biggest moves" card and a block at the top of each reading.
- Market comparison line on both ("S&P 500 was down 4.4%, so a lot of today was the whole market").
- "Since the last reading" items as mocked: lean change, Add more? label change, your-reason
  verdict change, new article count, earnings countdown.
- Analyst targets: A + B combined, including the situation-dependent closing sentence and the
  "analysts are often too optimistic" note.

## Design

### 1. Move context (computed, no AI) — new `move` field on Reading

Computed in `build_reading` from the price history already fetched:

- `date`: date of the last **completed** session in history ("last trading day"). The UI labels
  it with the date (e.g. "Thu Nov 5"). Scheduled readings (07:00 / 21:00 Manila) run after US
  close and before US open, so this is normally the last row. *(Designer call)* For a manual
  refresh while the US market is open: if the last row's date is today in America/New_York and
  NY time is before 16:15, that row is an in-progress session and is excluded from the move
  calculation (the move covers the previous completed day; the UI adds "US market is open; this
  covers the last completed day"). `price.day_change_pct` keeps its current behaviour.
- `change_pct`: last completed close vs the close before it.
- `typical_pct`: the ticker's normal daily swing = 30-day volatility / √252.
- `notable`: `abs(change_pct) >= max(1.5 × typical_pct, 1.0)`. *(designer call; thresholds go in
  `analysis/` constants so they're easy to tune.)*
- `biggest_since`: for notable moves, the most recent earlier date in the ~1-year history with a
  same-direction move at least as large; `None` means "biggest in the past year". UI phrases it as
  "its biggest one-day drop in 7 months". *(Designer call)* ≥ 1 month → months (rounded down);
  2–4 weeks → "in N weeks"; under 2 weeks → phrase omitted; `None` → "in the past year".
- `market_change_pct`: S&P 500 day change **on the same date**, using VOO price history (same
  baseline as the track record). Omitted when the ticker is VOO itself or the dates don't line up.
- `market_share`: plain-language band computed in code, not by AI:
  - same direction and market/stock ratio ≥ 0.8 → "mostly the whole market"
  - 0.35–0.8 → "roughly half was the whole market" *(phrasing: "a lot of" / "roughly half")*
  - < 0.35 → "mostly specific to this ticker"
  - opposite direction → "while the S&P 500 went the other way (+0.6%)"
  *(designer call on band edges.)*

- `market_notable`: whether the S&P 500's own move was unusual for it (same notable test applied
  to VOO's history: `abs(change) >= max(1.5 × VOO typical, 1.0)`). Feeds the dashboard header.

VOO history fetch: one extra yfinance call per reading, cached in memory for 1 hour so the morning
job (10 tickers) fetches it once. The market change is matched on the same completed-session date.
If it fails or dates don't line up, the market fields are omitted.

### 2. Move reason (AI, same request) — new `move_reason` on AISummary

- Add `move_reason: Claim | None` to `AISummary`.
- The prompt's computed data gains the move block (date, change, typical, notable, market change).
- Instruction: *only if `notable` is true*, write one sentence (≤ 25 words) on why the price moved
  on that date, citing article ids; if the articles don't explain it, leave `move_reason` empty.
  If not notable, leave it empty.
- Validation reuses the existing claim rule: invalid ids are dropped; a claim with no valid ids is
  dropped (→ UI shows "no company-specific news found").
- Readings that skip AI (fewer than 3 articles, budget exhausted) still get the computed move
  context; the reason line then says the AI read wasn't available, not "no news found".

### 3. Since the last reading (computed, no AI) — new `changes` field on Reading

Computed in `build_reading` before insert, against earlier readings of the same ticker:

- `since`: timestamp of the immediately previous reading (shown in the header).
- For **AI fields** (lean, your-reason verdict) compare with the most recent earlier reading whose
  `ai_status` was `ok`, so a budget-exhausted reading in between doesn't hide a lean flip. Your-
  reason verdict is compared only if both readings checked the same reason text. *(Designer call)*
  Each change item carries its own `since`; when an AI item's comparison reading differs from the
  header's, the UI appends it, e.g. "Lean: Bullish → Neutral (vs Nov 3)".
- For **computed fields** compare with the immediately previous reading:
  - Add more? label change (`price.label`),
  - hype warning appeared / cleared,
  - average analyst target moved ≥ 5% (e.g. "$327 → $310"),
  - new articles: count of source ids in this reading not present in the previous one.
- Earnings countdown is not a "change": show "earnings in N days" when ≤ 14 days away (local date).
- First reading of a ticker → no `changes` block.
- Stored on the reading payload (deterministic, visible later in history).

### 4. UI

**Reading page** — a new card first in the left column, above the chart: "Why it moved".
- Line 1: "**Down 9.3%** on Thu Nov 5 — its biggest one-day drop in 7 months." For non-notable
  moves: "Down 0.4% on Thu Nov 5 — a normal day for NVDA." (no reason line, no market line).
- Line 2 (notable + market data): "The S&P 500 fell 4.4% the same day, so roughly half of the drop
  was the whole market."
- Line 3 (notable): the AI reason with citation chips, or "No company-specific news found for this
  move." / "AI read not available for this reading."
- Sub-section "Since the last reading (yesterday 9:00 PM)": the change list; hidden when empty.
- Readings saved before this release have no `move`/`changes` fields: the card is hidden.

**Dashboard** — "Biggest moves" card near the top of the home page.
- Header line with the S&P 500 day change for the latest move date. *(Designer call)* The
  market-wide hint ("a big day for the whole market") appears only when `market_notable` is true;
  otherwise just the number.
- *(Designer call)* Only entries whose `move_date` equals the latest `move_date` across all
  entries are considered, so a stale reading never shows last week's move under "last trading
  day". If some tickers were skipped for that reason, a muted footnote says "N tickers not
  refreshed for this day".
- Rows: notable movers only, sorted by how unusual the move was (`|change| / typical`), max 5.
  Each row: ticker, % change, one-line reason (move reason text, or "about the same as the
  market; no company-specific news found", etc.). Click opens the reading. No citation chips on
  the dashboard (they're on the reading).
- No notable movers: "No unusual moves on the last trading day."
- Data comes from `/api/lists` entries: add `move_notable`, `move_change_pct`, `move_typical_pct`,
  `move_reason`, `market_change_pct`, `market_notable`, `move_date` to the list summary.

**Analyst targets card** (replaces the PR #6 strip), title "What analysts expect (12 months)":
- Sentence: "On average, **58 analysts** think NVDA will be around **$327** in a year. Today it's
  **$181.60**."
- Three boxes: Lowest / Average (highlighted) / Highest, each with "% from today".
- Closing sentence by position of today's price vs the range, checked in this order *(designer
  call on order and the "near highest" case)*:
  1. above highest: "Today's price is above every analyst's target, so they think it's run ahead."
  2. below lowest (any amount): "Today's price is below every analyst's target."
  3. at or up to 5% above lowest: "Today's price is right at the lowest guess — even the most
     cautious analyst expects about the same price."
  4. within 5% below highest: "Today's price is close to the highest guess."
  5. otherwise: "Today's price is between the lowest and highest guesses."
- Footer: "Average rating: Strong buy · These are analysts' opinions, not a Kairos forecast.
  Analysts are often too optimistic."
- Missing low/high → sentence + average box only. ETFs/uncovered stocks → card hidden (unchanged).
- Compare page row unchanged.

## Constraints

- Existing stack and patterns: FastAPI + pydantic models, `analysis/` for pure computations with
  unit tests, TanStack Query + Zod on the frontend (new fields optional for old payloads).
- TDD as in previous plans; backend + frontend checks green; Gemini schema change must keep the
  structured-output call working (test with the recorded/mocked client like existing tests).
- No `.env` changes required.

## Left to the builder

- Exact model/field names and where helper functions live.
- How the VOO cache is implemented (module-level TTL cache is fine).
- Card styling within the existing design system.
- Whether "Since the last reading" is computed with one or two queries.
