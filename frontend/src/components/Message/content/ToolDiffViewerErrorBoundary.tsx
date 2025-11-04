import React, { Component, ErrorInfo, ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error?: Error
}

/**
 * Error boundary for ToolDiffViewer component.
 *
 * Catches rendering errors in ToolDiffViewer and displays a fallback UI
 * instead of crashing the entire component tree. This prevents WebSocket
 * disconnection issues caused by component unmounting.
 *
 * Returns:
 *     Error boundary wrapper component
 */
class ToolDiffViewerErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log the error for debugging
    console.error('[ToolDiffViewerErrorBoundary] Caught error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      // Fallback UI when an error occurs
      return (
        <div className="tool-diff-viewer">
          <div className="diff-header">
            <div className="diff-file-info">
              <span className="diff-file-name" style={{ color: '#ef4444' }}>
                Error displaying diff viewer
              </span>
              <span className="diff-file-path" style={{ fontSize: '0.75rem', color: '#71717a' }}>
                {this.state.error?.message || 'Unknown error'}
              </span>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

export default ToolDiffViewerErrorBoundary
