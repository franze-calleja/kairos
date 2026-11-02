import type { Claim, NewsItem } from '../../api/schemas'

export function ClaimList({ claims, sources }: { claims: Claim[]; sources: NewsItem[] }) {
  const index = new Map(sources.map((s, i) => [s.id, { n: i + 1, url: s.url, title: s.title }]))
  return (
    <ul className="claims">
      {claims.map((claim, i) => (
        <li key={i}>
          {claim.text}{' '}
          {claim.source_ids.map((id) => {
            const ref = index.get(id)
            return ref ? (
              <a key={id} href={ref.url} target="_blank" rel="noopener noreferrer" title={ref.title} className="cite">
                [{ref.n}]
              </a>
            ) : null
          })}
        </li>
      ))}
    </ul>
  )
}
