import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="page shell" style={{ textAlign: 'center', paddingTop: 80 }}>
          <h2>Something went wrong</h2>
          <p className="error" style={{ marginBottom: 16 }}>
            {this.state.error?.message || 'An unexpected error occurred.'}
          </p>
          <a href="/" className="btn-secondary">Back to Search</a>
        </main>
      )
    }
    return this.props.children
  }
}
