import { apiError } from '../api/client'
import { usePortfolio } from '../api/hooks'

export const OWN_ALREADY_HELP =
  'Already own some? Log it as one buy at your average price (Gotrade shows it on the position).'

/** The owner's logged buys and sells: positions, returns vs VOO, and history. Local only. */
export function BuysPage() {
  const { data, isError, error } = usePortfolio()
  const empty = data && data.history.length === 0
  return (
    <article className="reading buys">
      <section className="card">
        <h1>My buys</h1>
        <p className="muted small">Stays on your machine; never sent to the AI.</p>
      </section>
      {isError && <p className="error-box">{apiError(error)}</p>}
      {empty && (
        <section className="card">
          <p>Log your buys to see your average cost, gains and how they compare with simply buying VOO.</p>
          <p className="muted small">{OWN_ALREADY_HELP}</p>
        </section>
      )}
    </article>
  )
}
