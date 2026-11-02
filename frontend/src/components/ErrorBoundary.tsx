import { Component, type ErrorInfo, type ReactNode } from 'react'

interface State {
  error: Error | null
}

/** Keeps one broken view (e.g. the chart rejecting odd data) from blanking the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Kairos view crashed', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="error-box crash" role="alert">
        <p>
          <b>Something went wrong showing this view.</b>
        </p>
        <p className="small">{this.state.error.message}</p>
        <button type="button" className="primary" onClick={() => this.setState({ error: null })}>
          Try again
        </button>
      </div>
    )
  }
}
