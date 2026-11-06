import { z } from 'zod'

const num = z.number().nullable()

export const LeanSchema = z.enum(['bullish', 'neutral', 'bearish'])
export const AIStatusSchema = z.enum([
  'ok',
  'not_enough_signal',
  'budget_exhausted',
  'unavailable',
  'not_configured',
])

export const ListEntrySchema = z.object({
  ticker: z.string(),
  lean: LeanSchema.nullable(),
  ai_status: AIStatusSchema.nullable(),
  name: z.string().nullable().default(null),
  kind: z.enum(['stock', 'etf']).nullable().default(null),
  price: z.number().nullable().default(null),
  day_change_pct: z.number().nullable().default(null),
  price_label: z.enum(['stretched', 'near_average', 'below_range', 'insufficient_history']).nullable().default(null),
  next_earnings: z.string().nullable().default(null),
  hype_warning: z.boolean().nullable().default(null),
  updated_at: z.string().nullable().default(null),
  shares: z.number().nullable().default(null),
  shares_source: z.enum(['trades', 'manual']).nullable().default(null),
  thesis: z.string().nullable().default(null),
  thesis_verdict: z.enum(['supports', 'challenges', 'mixed', 'no_signal']).nullable().default(null),
  move_date: z.string().nullable().default(null),
  move_notable: z.boolean().nullable().default(null),
  move_change_pct: z.number().nullable().default(null),
  move_typical_pct: z.number().nullable().default(null),
  move_reason: z.string().nullable().default(null),
  market_change_pct: z.number().nullable().default(null),
  market_notable: z.boolean().nullable().default(null),
})
export const ListsSchema = z.object({
  holdings: z.array(ListEntrySchema),
  watching: z.array(ListEntrySchema),
})

export const SourceStatusSchema = z.object({
  name: z.enum(['yfinance', 'finnhub', 'google_news', 'sec', 'reddit', 'gemini']),
  status: z.enum(['ok', 'error', 'disabled', 'not_configured']),
  detail: z.string().nullable().optional(),
})

export const NewsItemSchema = z.object({
  id: z.string(),
  source: z.string(),
  title: z.string(),
  summary: z.string(),
  url: z.string(),
  published_at: z.string(),
  related_ticker: z.string(),
  weight: z.number(),
  outlet: z.string().nullable().optional(),
})

export const PriceContextSchema = z.object({
  last_price: z.number(),
  day_change_pct: num,
  ma50: num,
  ma200: num,
  pct_vs_ma50: num,
  pct_vs_ma200: num,
  high_52w: z.number(),
  low_52w: z.number(),
  pct_from_52w_high: z.number(),
  volatility_30d: num,
  label: z.enum(['stretched', 'near_average', 'below_range', 'insufficient_history']),
  history: z.array(z.object({ date: z.string(), close: z.number() })),
})

export const EventsSchema = z.object({
  next_earnings: z.string().nullable(),
  earnings_within_7d: z.boolean(),
  next_ex_dividend: z.string().nullable(),
  macro: z.array(z.object({ date: z.string(), kind: z.enum(['FOMC', 'CPI']) })),
})

export const HoldingSchema = z.object({ symbol: z.string(), name: z.string(), weight: z.number() })

export const QuickNumbersSchema = z.object({
  kind: z.enum(['stock', 'etf']),
  market_cap: num,
  trailing_pe: num,
  forward_pe: num,
  sector: z.string().nullable(),
  sector_pe: num,
  revenue_growth: num,
  profit_margin: num,
  expense_ratio: num,
  aum: num,
  top_holdings: z.array(HoldingSchema),
  target_mean: z.number().nullable().optional(),
  target_median: z.number().nullable().optional(),
  target_low: z.number().nullable().optional(),
  target_high: z.number().nullable().optional(),
  analyst_count: z.number().nullable().optional(),
  analyst_rating: z.string().nullable().optional(),
})

export const HypeFlagSchema = z.object({
  code: z.enum([
    'attention_spike_no_substance',
    'micro_cap',
    'price_spike',
    'otc',
    'penny',
    'low_volume',
  ]),
  triggered: z.boolean(),
  value: z.string(),
})

export const ClaimSchema = z.object({ text: z.string(), source_ids: z.array(z.string()) })

export const ThesisCheckSchema = z.object({
  verdict: z.enum(['supports', 'challenges', 'mixed', 'no_signal']),
  text: z.string(),
  source_ids: z.array(z.string()),
})

export const AISummarySchema = z.object({
  lean: LeanSchema,
  confidence: z.enum(['low', 'medium', 'high']),
  not_enough_signal: z.boolean(),
  substantive_news: z.boolean(),
  drivers: z.array(ClaimSchema),
  bull_case: z.array(ClaimSchema),
  bear_case: z.array(ClaimSchema),
  takeaway: ClaimSchema.nullable().optional(),
  thesis_check: ThesisCheckSchema.nullable().optional(),
  move_reason: ClaimSchema.nullable().optional(),
})

export const MoveSchema = z.object({
  date: z.string(),
  change_pct: z.number(),
  typical_pct: num,
  notable: z.boolean(),
  biggest_since: z.string().nullable().optional(),
  market_open: z.boolean().optional(),
  history_start: z.string().nullable().optional(),
  market_change_pct: z.number().nullable().optional(),
  market_notable: z.boolean().nullable().optional(),
  market_share: z.enum(['market', 'half', 'ticker', 'opposite']).nullable().optional(),
})

export const ChangeItemSchema = z.object({
  kind: z.enum(['lean', 'verdict', 'price_label', 'hype', 'target', 'new_articles']),
  before: z.string().nullable().optional(),
  after: z.string().nullable().optional(),
  count: z.number().nullable().optional(),
  since: z.string(),
})

export const ChangesSchema = z.object({ since: z.string(), items: z.array(ChangeItemSchema) })

export const ReadingSchema = z.object({
  ticker: z.string(),
  name: z.string(),
  kind: z.enum(['stock', 'etf']),
  created_at: z.string(),
  price: PriceContextSchema.nullable(),
  events: EventsSchema,
  quick: QuickNumbersSchema,
  hype: z.array(HypeFlagSchema),
  ai: AISummarySchema.nullable(),
  ai_status: AIStatusSchema,
  sources: z.array(NewsItemSchema),
  data_health: z.array(SourceStatusSchema),
  thesis_checked: z.string().nullable().optional(),
  move: MoveSchema.nullable().optional(),
  changes: ChangesSchema.nullable().optional(),
})

const HorizonStatsSchema = z.object({
  n: z.number(),
  avg_change_pct: num,
  avg_excess_pct: num,
  pct_positive: num,
})
export const TrackRecordSchema = z.object({
  by_lean: z.record(LeanSchema, z.record(z.string(), HorizonStatsSchema)),
  small_sample: z.boolean(),
})

export const DiscoverSchema = z.object({
  items: z.array(z.object({ ticker: z.string(), reason: z.string(), score: z.number() })),
  created_at: z.string().nullable(),
  spike_scan: z.enum(['ok', 'not_configured', 'error']).nullable(),
})

export const SettingsSchema = z.object({
  gemini_configured: z.boolean(),
  finnhub_configured: z.boolean(),
  sec_configured: z.boolean(),
  reddit_enabled: z.boolean(),
  gemini_model: z.string(),
  budget: z.object({ minute: z.number(), day: z.number(), rpm: z.number(), rpd: z.number() }),
  morning_refresh_time: z.string(),
  evening_refresh_time: z.string().nullable().default(null),
  last_evening_run: z.string().nullable().default(null),
  last_backup: z.string().nullable().default(null),
  backup_dir: z.string().nullable().default(null),
  backup_keep: z.number().default(14),
  tz: z.string(),
  reading_cache_hours: z.number(),
  last_morning_run: z.string().nullable(),
  thresholds: z.record(z.string(), z.number()),
})

export type Lean = z.infer<typeof LeanSchema>
export type AIStatus = z.infer<typeof AIStatusSchema>
export type ListEntry = z.infer<typeof ListEntrySchema>
export type Lists = z.infer<typeof ListsSchema>
export type Reading = z.infer<typeof ReadingSchema>
export type NewsItem = z.infer<typeof NewsItemSchema>
export type Claim = z.infer<typeof ClaimSchema>
export type AISummary = z.infer<typeof AISummarySchema>
export type TrackRecord = z.infer<typeof TrackRecordSchema>
export type Discover = z.infer<typeof DiscoverSchema>
export type Settings = z.infer<typeof SettingsSchema>
export type ListName = 'holdings' | 'watching'

export const JobStatusSchema = z.object({
  running: z.boolean(),
  kind: z.enum(['morning', 'evening']).nullable().default(null),
  phase: z.enum(['readings', 'outcomes', 'discover']).nullable(),
  done: z.number(),
  total: z.number(),
  current: z.string().nullable(),
  started_at: z.string().nullable(),
  last_run: z.string().nullable(),
})
export type JobStatus = z.infer<typeof JobStatusSchema>

export const ExposureSchema = z.object({
  total_value: z.number(),
  positions: z.array(
    z.object({
      ticker: z.string(),
      shares: z.number(),
      price: z.number(),
      value: z.number(),
      weight: z.number(),
      name: z.string().nullable(),
      kind: z.enum(['stock', 'etf']),
    }),
  ),
  underlying: z.array(
    z.object({
      symbol: z.string(),
      name: z.string(),
      weight: z.number(),
      direct: z.number(),
      via: z.record(z.string(), z.number()),
    }),
  ),
  rest_of_funds: z.number(),
  sectors: z.array(z.object({ sector: z.string(), weight: z.number() })),
  missing_prices: z.array(z.string()),
})
export type Exposure = z.infer<typeof ExposureSchema>
export type ThesisCheck = z.infer<typeof ThesisCheckSchema>
export type Move = z.infer<typeof MoveSchema>
export type ChangeItem = z.infer<typeof ChangeItemSchema>
export type Changes = z.infer<typeof ChangesSchema>

export const TradeSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  side: z.enum(['buy', 'sell']),
  trade_date: z.string(),
  shares: z.number(),
  price: z.number(),
  created_at: z.string(),
})

export const PositionSchema = z.object({
  ticker: z.string(),
  shares: z.number(),
  avg_cost: num,
  invested: z.number(),
  value: num,
  gain: num,
  gain_pct: num,
  realized: z.number(),
  total_bought: z.number(),
  sell_proceeds: z.number(),
  return_pct: num,
  voo_pct: num,
})

export const KairosSaidSchema = z.object({
  price_label: z.enum(['stretched', 'near_average', 'below_range', 'insufficient_history']).nullable(),
  lean: LeanSchema.nullable(),
  ai_status: AIStatusSchema,
})

export const HistoryRowSchema = z.object({
  id: z.number(),
  ticker: z.string(),
  side: z.enum(['buy', 'sell']),
  trade_date: z.string(),
  shares: z.number(),
  price: z.number(),
  amount: z.number(),
  kairos_said: KairosSaidSchema.nullable(),
  since_pct: num,
  voo_since_pct: num,
})

export const PortfolioSchema = z.object({
  positions: z.array(PositionSchema),
  totals: z.object({ invested: z.number(), value: num, gain: num, return_pct: num, voo_pct: num }),
  realized: z.number(),
  history: z.array(HistoryRowSchema),
})

export const CloseSchema = z.object({ date: z.string(), close: z.number() })

export type Trade = z.infer<typeof TradeSchema>
export type Position = z.infer<typeof PositionSchema>
export type HistoryRow = z.infer<typeof HistoryRowSchema>
export type Portfolio = z.infer<typeof PortfolioSchema>
