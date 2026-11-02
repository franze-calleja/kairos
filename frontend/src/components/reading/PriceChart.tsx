import { createChart, LineSeries } from 'lightweight-charts'
import { useEffect, useRef } from 'react'

type Point = { date: string; close: number }

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
  useEffect(() => {
    if (!ref.current || history.length === 0) return
    const chart = createChart(ref.current, {
      height: 220,
      autoSize: true,
      layout: { textColor: '#6b7280', attributionLogo: true },
      grid: { vertLines: { visible: false }, horzLines: { color: '#f3f4f6' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    })
    chart.addSeries(LineSeries, { color: '#4f46e5', lineWidth: 2 }).setData(
      history.map((p) => ({ time: p.date, value: p.close })),
    )
    chart.addSeries(LineSeries, { color: '#9ca3af', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }).setData(movingAverage(history, 50))
    chart.addSeries(LineSeries, { color: '#f59e0b', lineWidth: 1, priceLineVisible: false, lastValueVisible: false }).setData(movingAverage(history, 200))
    chart.timeScale().fitContent()
    return () => chart.remove()
  }, [history])
  return (
    <div className="chart-wrap">
      <div ref={ref} className="chart" />
      <p className="muted small legend">
        <span className="dot dot-price" /> price <span className="dot dot-ma50" /> 50-day avg <span className="dot dot-ma200" /> 200-day avg
      </p>
    </div>
  )
}
