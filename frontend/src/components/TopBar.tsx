import { useState, type FormEvent } from 'react'
import { normalizeTicker } from '../api/tickers'
import { useSelection } from '../store/selection'
import { useTheme } from '../store/theme'
import { LogoMark } from './Logo'
import { RefreshStatus } from './RefreshStatus'

function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
      title={dark ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {dark ? '☀︎' : '☾'}
    </button>
  )
}

export function TopBar() {
  const [value, setValue] = useState('')
  const select = useSelection((s) => s.select)
  const setView = useSelection((s) => s.setView)
  const showTrackRecord = useSelection((s) => s.showTrackRecord)
  const goHome = useSelection((s) => s.goHome)

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
        <button type="button" onClick={() => useSelection.getState().openCompare()}>
          Compare
        </button>
        <button type="button" onClick={() => setView('buys')}>
          My buys
        </button>
        <button type="button" onClick={() => setView('exposure')}>
          Exposure
        </button>
        <button type="button" onClick={() => showTrackRecord(null)}>
          Track record
        </button>
        <button type="button" onClick={() => setView('settings')}>
          Settings
        </button>
        <ThemeToggle />
      </nav>
    </header>
  )
}
