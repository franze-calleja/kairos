import { ComparePage } from './components/ComparePage'
import { Disclaimer } from './components/Disclaimer'
import { ErrorBoundary } from './components/ErrorBoundary'
import { BuysPage } from './components/BuysPage'
import { ExposurePage } from './components/ExposurePage'
import { Overview } from './components/Overview'
import { ReadingPanel } from './components/ReadingPanel'
import { SettingsPage } from './components/SettingsPage'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { TrackRecordPanel } from './components/TrackRecordPanel'
import { useSelection } from './store/selection'

function Main() {
  const { selected, view, trackTicker } = useSelection()
  if (view === 'settings') return <SettingsPage />
  if (view === 'exposure') return <ExposurePage />
  if (view === 'buys') return <BuysPage />
  if (view === 'compare') return <ComparePage />
  if (view === 'track') return <TrackRecordPanel key={trackTicker ?? 'all'} ticker={trackTicker ?? undefined} />
  if (!selected) return <Overview />
  return <ReadingPanel key={selected} ticker={selected} />
}

export default function App() {
  const { selected, view, trackTicker } = useSelection()
  return (
    <div className="app">
      <TopBar />
      <div className="layout">
        <Sidebar />
        <main className="main">
          <ErrorBoundary key={`${view}-${selected ?? ''}-${trackTicker ?? ''}`}>
            <Main />
          </ErrorBoundary>
        </main>
      </div>
      <Disclaimer />
    </div>
  )
}
