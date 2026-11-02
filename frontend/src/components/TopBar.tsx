import { useState, type FormEvent } from 'react'
import { useSelection } from '../store/selection'

export function TopBar() {
  const [value, setValue] = useState('')
  const select = useSelection((s) => s.select)
  const setView = useSelection((s) => s.setView)

  function submit(e: FormEvent) {
    e.preventDefault()
    const ticker = value.trim().toUpperCase()
    if (!ticker) return
    select(ticker)
    setValue('')
  }

  return (
    <header className="topbar">
      <span className="brand">KAIROS</span>
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
      <nav className="topnav">
        <button type="button" onClick={() => setView('track')}>
          Track record
        </button>
        <button type="button" onClick={() => setView('settings')}>
          Settings
        </button>
      </nav>
    </header>
  )
}
