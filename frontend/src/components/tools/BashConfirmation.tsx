import React, { useEffect } from 'react'
import { useBashConfirmation } from './hooks'
import './ToolStateDisplay.css'

/**
 * Global Bash Confirmation Component
 *
 * This component handles bash command confirmation requests globally.
 * It should be placed at the application level to avoid duplicate
 * event listeners and ensure only one confirmation dialog is active.
 */
const BashConfirmation: React.FC = () => {
  const { request: bashRequest, isOpen: bashConfirmationOpen, approve, reject } = useBashConfirmation()

  // Debug logging for component state
  useEffect(() => {
    console.log('[BashConfirmation] Component render state:', {
      bashConfirmationOpen,
      bashRequest,
      shouldShow: !!(bashConfirmationOpen && bashRequest)
    })
  }, [bashConfirmationOpen, bashRequest])

  console.log('[BashConfirmation] Render check:', {
    isOpen: bashConfirmationOpen,
    hasRequest: !!bashRequest,
    command: bashRequest?.command
  })

  if (!bashConfirmationOpen || !bashRequest) {
    return null
  }

  // 保持可见但样式更合适的版本
  return (
    <div style={{
      marginTop: '8px',
      padding: '12px',
      backgroundColor: 'rgba(239, 68, 68, 0.1)',
      border: '2px solid rgba(239, 68, 68, 0.3)',
      borderRadius: '8px',
      position: 'relative',
      zIndex: 10
    }}>
      <div style={{ marginBottom: '8px', fontSize: '13px', fontWeight: 600, color: '#dc2626' }}>
        <strong>Bash Command Confirmation:</strong>
      </div>
      <div style={{
        marginBottom: '12px',
        padding: '6px 8px',
        backgroundColor: 'rgba(0, 0, 0, 0.05)',
        borderRadius: '4px',
        border: '1px solid rgba(0, 0, 0, 0.1)'
      }}>
        <code style={{
          fontFamily: 'Monaco, Consolas, Courier New, monospace',
          fontSize: '12px',
          color: '#dc2626',
          fontWeight: 500
        }}>
          {bashRequest.command}
        </code>
      </div>
      <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
        <button
          onClick={() => reject('Command rejected by user')}
          style={{
            padding: '6px 12px',
            backgroundColor: 'rgba(239, 68, 68, 0.2)',
            color: '#dc2626',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.3)'}
          onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.2)'}
        >
          Reject
        </button>
        <button
          onClick={() => approve()}
          style={{
            padding: '6px 12px',
            backgroundColor: 'rgba(34, 197, 94, 0.2)',
            color: '#059669',
            border: '1px solid rgba(34, 197, 94, 0.3)',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s ease'
          }}
          onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(34, 197, 94, 0.3)'}
          onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(34, 197, 94, 0.2)'}
        >
          Approve
        </button>
      </div>
    </div>
  )
}

export default BashConfirmation