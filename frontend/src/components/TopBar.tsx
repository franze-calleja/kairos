import { useState, type FormEvent } from 'react'
import { normalizeTicker } from '../api/tickers'
import { useSelection } from '../store/selection'
import { LogoMark } from './Logo'
import { RefreshStatus } from './RefreshStatus'

export function TopBar() {
  const [value, setValue] = useState('')
  const select = useSelection((s) => s.select)
  const setView = useSelection((s) => s.setView)
  const showTrackRecord = useSelection((s) => s.showTrackRecord)
  const goHome = () => useSelection.setState({ selected: null, view: 'reading' })

  function submit(e: FormEvent) {
    e.preventDefault()
    const ticker = normalizeTicker(value)
    if (!ticker) return
    select(ticker)
    setValue('')
  }

  return (
    <header className="topbar">
      <button type="button" className="brand" onClick={goHome} aria-label="Kairos home">
        <LogoMark size={24} />
        <span className="wordmark">kairos</span>
      </button>
      <form onSubmit={submit} className="search" role="search">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Check any ticker…"
          aria-label="Check any ticker"
          autoComplete="off"
          spellCheck={false}
        />
      </form>
      <RefreshStatus />
      <nav className="topnav">
        <button type="button" onClick={() => showTrackRecord(null)}>
          Track record
        </button>
        <button type="button" onClick={() => setView('settings')}>
          Settings
        </button>
      </nav>
    </header>
  )
}
