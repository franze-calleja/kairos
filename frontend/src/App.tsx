import { Disclaimer } from './components/Disclaimer'
import { Sidebar } from './components/Sidebar'
import { TopBar } from './components/TopBar'
import { useSelection } from './store/selection'

export default function App() {
  const selected = useSelection((s) => s.selected)
  return (
    <div className="app">
      <TopBar />
      <div className="layout">
        <Sidebar />
        <main className="main">
          {selected ? (
            <p className="muted">Reading for {selected}</p>
          ) : (
            <div className="empty">
              <h1>Pick a ticker</h1>
              <p className="muted">Choose one from the sidebar or type any ticker in the search bar.</p>
            </div>
          )}
        </main>
      </div>
      <Disclaimer />
    </div>
  )
}
