import type { Reading } from '../../api/schemas'
import { daysBetween } from '../format'
import { Card } from './Card'

export function EventsCard({ events, asOf }: { events: Reading['events']; asOf: string }) {
  const empty = !events.next_earnings && !events.next_ex_dividend && events.macro.length === 0
  return (
    <Card title="Upcoming events">
      {events.earnings_within_7d && events.next_earnings && (
        <p className="badge badge-warn">Earnings in {daysBetween(asOf, events.next_earnings)} days</p>
      )}
      <ul className="plain">
        {events.next_earnings && <li>Earnings: {events.next_earnings}</li>}
        {events.next_ex_dividend && <li>Ex-dividend: {events.next_ex_dividend}</li>}
        {events.macro.map((m) => (
          <li key={`${m.kind}-${m.date}`}>
            {m.kind === 'FOMC' ? 'Fed rate decision' : 'CPI inflation report'}: {m.date}
          </li>
        ))}
      </ul>
      {empty && <p className="muted small">Nothing scheduled in the next 30 days.</p>}
    </Card>
  )
}
