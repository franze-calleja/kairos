import { Disclaimer } from './components/Disclaimer'
import { ReadingPanel } from './components/ReadingPanel'
import { SettingsPage } from './components/SettingsPage'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { TrackRecordPanel } from './components/TrackRecordPanel'
import { useSelection } from './store/selection'

function Main() {
  const { selected, view, trackTicker } = useSelection()
  if (view === 'settings') return <SettingsPage />
  if (view === 'track') return <TrackRecordPanel key={trackTicker ?? 'all'} ticker={trackTicker ?? undefined} />
  if (!selected) {
    return (
      <div className="empty">
        <h1>Pick a ticker</h1>
        <p className="muted">Choose one from the sidebar or type any ticker in the search bar.</p>
      </div>
    )
  }
  return <ReadingPanel key={selected} ticker={selected} />
}

export default function App() {
  return (
    <div className="app">
      <TopBar />
      <div className="layout">
        <Sidebar />
        <main className="main">
          <Main />
        </main>
      </div>
      <Disclaimer />
    </div>
  )
}
