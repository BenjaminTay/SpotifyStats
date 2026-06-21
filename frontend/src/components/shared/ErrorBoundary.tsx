import { Component } from 'react'

interface ErrorBoundaryProps {
  children: React.ReactNode
  fallback?: React.ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      if (import.meta.env.DEV) {
        console.error('ErrorBoundary caught:', this.state.error)
      }
      if (this.props.fallback) return this.props.fallback
      return (
        <div className="py-16 text-center">
          <p className="font-serif text-[28px] font-bold mb-3">页面渲染错误</p>
          {import.meta.env.DEV && (
            <p className="font-sans text-[13px] text-muted-foreground mb-4 font-mono whitespace-pre-wrap break-all max-w-lg mx-auto">
              {this.state.error.message}
            </p>
          )}
          <p className="font-sans text-[13px] text-muted-foreground/60">
            请刷新页面后重试。如问题持续，请联系管理员。
          </p>
        </div>
      )
    }
    return this.props.children
  }
}

export { ErrorBoundary }
