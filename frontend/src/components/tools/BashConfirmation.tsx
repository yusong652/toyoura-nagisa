import React, { useEffect, useState, useRef } from 'react'
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
  const { currentRequest: bashRequest, isOpen: bashConfirmationOpen, approve, reject } = useBashConfirmation()

  // All hooks must be called before any conditional returns
  const [selectedButton, setSelectedButton] = useState<'reject' | 'approve'>('approve') // Default to approve
  const containerRef = useRef<HTMLDivElement>(null)
  const rejectButtonRef = useRef<HTMLButtonElement>(null)
  const approveButtonRef = useRef<HTMLButtonElement>(null)

  // Debug logging for component state
  useEffect(() => {

  }, [bashConfirmationOpen, bashRequest])

  // Conditional return MUST come after all hooks

  // Handle keyboard navigation - only when component should be visible
  useEffect(() => {
    if (!bashConfirmationOpen || !bashRequest) return

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowUp':
        case 'ArrowLeft':
          e.preventDefault()
          setSelectedButton('reject')
          break
        case 'ArrowDown':
        case 'ArrowRight':
          e.preventDefault()
          setSelectedButton('approve')
          break
        case 'Enter':
          e.preventDefault()
          if (selectedButton === 'approve') {
            approve()
          } else {
            reject('Command rejected by user')
          }
          break
        case 'y':
        case 'Y':
          e.preventDefault()
          approve()
          break
        case 'n':
        case 'N':
          e.preventDefault()
          reject('Command rejected by user')
          break
        case 'Escape':
          e.preventDefault()
          reject('Command rejected by user')
          break
      }
    }

    // Focus the container to enable keyboard events
    if (containerRef.current) {
      containerRef.current.focus()
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [bashConfirmationOpen, bashRequest, selectedButton, approve, reject])

  // Now safe to return conditionally after all hooks are called
  if (!bashConfirmationOpen || !bashRequest) {
    return null
  }

  // Simple styling matching ToolStateDisplay design
  return (
    <div
      ref={containerRef}
      tabIndex={0}
      style={{
        marginTop: '2px',
        padding: '8px',
        background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(220, 38, 38, 0.04) 100%)',
        border: '1px solid rgba(239, 68, 68, 0.15)',
        borderRadius: '16px',
        position: 'relative',
        zIndex: 10,
        width: '400px',
        maxWidth: '400px',
        minWidth: '400px',
        outline: 'none',
        backdropFilter: 'blur(20px) saturate(150%)',
        WebkitBackdropFilter: 'blur(20px) saturate(150%)',
        boxShadow: '0 4px 20px rgba(239, 68, 68, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05), inset 0 1px 0 rgba(255, 255, 255, 0.1)'
      }}>
      <div style={{
        marginBottom: '6px',
        padding: '6px 8px',
        background: 'linear-gradient(135deg, rgba(0, 0, 0, 0.03) 0%, rgba(0, 0, 0, 0.01) 100%)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        borderRadius: '8px',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)'
      }}>
        <code style={{
          fontFamily: 'Monaco, Consolas, Courier New, monospace',
          fontSize: '12px',
          color: '#71717a',
          fontWeight: 400,
          opacity: 0.9,
          letterSpacing: '0.2px',
          userSelect: 'text',
          cursor: 'text'
        }}>
          {bashRequest.command}
        </code>
      </div>
      <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', fontSize: '12px' }}>
        <button
          ref={rejectButtonRef}
          onClick={() => reject('Command rejected by user')}
          onMouseEnter={() => setSelectedButton('reject')}
          style={{
            background: 'none',
            border: 'none',
            color: selectedButton === 'reject' ? '#dc2626' : '#71717a',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: selectedButton === 'reject' ? 600 : 400,
            fontFamily: 'Monaco, Consolas, Courier New, monospace',
            padding: '2px 4px',
            textDecoration: selectedButton === 'reject' ? 'underline' : 'none'
          }}
        >
          [n] reject
        </button>
        <button
          ref={approveButtonRef}
          onClick={() => approve()}
          onMouseEnter={() => setSelectedButton('approve')}
          style={{
            background: 'none',
            border: 'none',
            color: selectedButton === 'approve' ? '#059669' : '#71717a',
            cursor: 'pointer',
            fontSize: '12px',
            fontWeight: selectedButton === 'approve' ? 600 : 400,
            fontFamily: 'Monaco, Consolas, Courier New, monospace',
            padding: '2px 4px',
            textDecoration: selectedButton === 'approve' ? 'underline' : 'none'
          }}
        >
          [y] approve
        </button>
      </div>
    </div>
  )
}

export default BashConfirmation