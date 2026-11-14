import React from 'react'

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null, errorInfo: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
    this.setState({ errorInfo })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-slate-900 text-white flex items-center justify-center p-6">
          <div className="max-w-2xl w-full bg-slate-800 border border-red-500/30 rounded-2xl p-8 shadow-2xl">
            <div className="flex items-center space-x-3 text-red-400 mb-4">
              <span className="text-2xl">⚠️</span>
              <h1 className="text-xl font-bold">Application Error Detected</h1>
            </div>
            <p className="text-sm text-gray-300 mb-4">
              A runtime component error occurred. Here are the diagnostic details:
            </p>
            <div className="bg-black/60 p-4 rounded-xl text-xs font-mono text-red-300 overflow-x-auto mb-6">
              {this.state.error?.toString()}
            </div>
            {this.state.errorInfo?.componentStack && (
              <details className="text-xs font-mono text-gray-400 bg-black/30 p-3 rounded-lg mb-6">
                <summary className="cursor-pointer text-gray-300 font-semibold mb-2">Component Stack Trace</summary>
                <pre className="whitespace-pre-wrap">{this.state.errorInfo.componentStack}</pre>
              </details>
            )}
            <div className="flex space-x-4">
              <button
                onClick={() => {
                  localStorage.clear()
                  window.location.href = '/login'
                }}
                className="bg-teal-600 hover:bg-teal-700 text-white px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              >
                Clear Session & Return to Login
              </button>
              <button
                onClick={() => window.location.reload()}
                className="bg-slate-700 hover:bg-slate-600 text-gray-200 px-4 py-2 rounded-lg text-sm font-semibold transition-colors"
              >
                Reload Page
              </button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
