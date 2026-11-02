import { createChart, LineSeries } from 'lightweight-charts'
import { useEffect, useRef, useState } from 'react'

type Point = { date: string; close: number }
const RANGES = { '1M': 21, '6M': 126, '1Y': Infinity } as const
type Range = keyof typeof RANGES

function movingAverage(points: Point[], window: number) {
  const out: { time: string; value: number }[] = []
  let sum = 0
  points.forEach((p, i) => {
    sum += p.close
    if (i >= window) sum -= points[i - window].close
    if (i >= window - 1) out.push({ time: p.date, value: sum / window })
  })
  return out
}

export function PriceChart({ history }: { history: Point[] }) {
  const ref = useRef<HTMLDivElement>(null)
  const [range, setRange] = useState<Range>('1Y')

  useEffect(() => {
    if (!ref.current || history.length === 0) return
    const visible = history.slice(-Math.min(RANGES[range], history.length))
    const from = visible[0].date
    // Averages use the full history, then get clipped to the visible window.
    const clip = (pts: { time: string; value: number }[]) => pts.filter((p) => p.time >= from)
    const chart = createChart(ref.current, {
      height: 240,
      autoSize: true,
      layout: { textColor: '#6b7280', attributionLogo: true },
      grid: { vertLines: { visible: false }, horzLines: { color: '#f3f4f6' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    })
    chart.addSeries(LineSeries, { color: '#4f46e5', lineWidth: 2 }).setData(
      visible.map((p) => ({ time: p.date, value: p.close })),
    )
    const quiet = { lineWidth: 1, priceLineVisible: false, lastValueVisible: false } as const
    chart.addSeries(LineSeries, { color: '#9ca3af', ...quiet }).setData(clip(movingAverage(history, 50)))
    chart.addSeries(LineSeries, { color: '#f59e0b', ...quiet }).setData(clip(movingAverage(history, 200)))
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [history, range])

  return (
    <div className="chart-wrap">
      <div className="chart-top">
        <p className="muted small legend">
          <span className="dot dot-price" /> price <span className="dot dot-ma50" /> 50-day avg{' '}
          <span className="dot dot-ma200" /> 200-day avg
        </p>
        <div className="ranges" role="group" aria-label="Chart period">
          {(Object.keys(RANGES) as Range[]).map((r) => (
            <button key={r} type="button" aria-pressed={range === r} onClick={() => setRange(r)}>
              {r}
            </button>
          ))}
        </div>
      </div>
      <div ref={ref} className="chart" />
    </div>
  )
}
