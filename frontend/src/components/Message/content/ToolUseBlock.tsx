import React, { useState, useEffect, useCallback, useRef } from 'react'
import { ToolUseBlock as ToolUseBlockType } from '../../../types/chat'

interface ToolUseBlockProps {
  block: ToolUseBlockType
}

type ConfirmationStatus = 'pending' | 'approved' | 'rejected'

/**
 * Tool use block component for displaying tool calls.
 *
 * Shows the tool name, input parameters in a collapsible format.
 * For bash tool, displays interactive command confirmation UI inline.
 * Supports multiple tool calls in a single message.
 *
 * Args:
 *     block: ToolUseBlock object with tool name and input parameters
 *
 * Returns:
 *     JSX element with tool call display
 */
const ToolUseBlock: React.FC<ToolUseBlockProps> = ({ block }) => {
  const [isExpanded, setIsExpanded] = useState(false)
  const [confirmationStatus, setConfirmationStatus] = useState<ConfirmationStatus>('approved') // Default to approved for historical messages
  const [selectedButton, setSelectedButton] = useState<'reject' | 'approve'>('approve')
  const [currentConfirmationId, setCurrentConfirmationId] = useState<string | null>(null)

  const blockIdRef = useRef(block.id)

  const hasInput = block.input && Object.keys(block.input).length > 0

  // Check if this is a bash tool call with command parameter
  const isBashTool = block.name === 'bash'
  const bashCommand = isBashTool && block.input?.command ? block.input.command : null

  // Send confirmation response via WebSocket
  const sendConfirmationResponse = useCallback(async (confirmationId: string, approved: boolean, userMessage?: string) => {
    let ws = (window as any).__wsConnection

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      const waitForConnection = (window as any).__waitForConnection
      if (waitForConnection) {
        const connected = await waitForConnection(3000)
        if (connected) {
          ws = (window as any).__wsConnection
        } else {
          console.error('[ToolUseBlock] Failed to get WebSocket connection')
          return
        }
      }
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      const response = {
        type: 'BASH_CONFIRMATION_RESPONSE',
        confirmation_id: confirmationId,
        approved,
        user_message: userMessage,
        timestamp: new Date().toISOString()
      }

      try {
        ws.send(JSON.stringify(response))
        console.log(`[ToolUseBlock] Sent confirmation response: ${approved ? 'approved' : 'rejected'}`)
      } catch (error) {
        console.error('[ToolUseBlock] Error sending confirmation response:', error)
      }
    }
  }, [])

  // Handle approval
  const handleApprove = useCallback(() => {
    if (currentConfirmationId) {
      sendConfirmationResponse(currentConfirmationId, true)
      setConfirmationStatus('approved')
      setCurrentConfirmationId(null)
    }
  }, [currentConfirmationId, sendConfirmationResponse])

  // Handle rejection
  const handleReject = useCallback(() => {
    if (currentConfirmationId) {
      sendConfirmationResponse(currentConfirmationId, false, 'Command rejected by user')
      setConfirmationStatus('rejected')
      setCurrentConfirmationId(null)

      // Dispatch event to clear tool state
      window.dispatchEvent(new CustomEvent('toolUseConcluded', {
        detail: {
          reason: 'user_rejection',
          timestamp: new Date().toISOString()
        }
      }))
    }
  }, [currentConfirmationId, sendConfirmationResponse])

  // Listen for bash confirmation requests
  useEffect(() => {
    const handleBashConfirmationRequest = (event: CustomEvent) => {
      const data = event.detail

      // Match this confirmation request to this tool block by checking if:
      // 1. It's a bash command
      // 2. The command matches (if available)
      // 3. The timing is recent (within last few seconds)
      if (isBashTool && bashCommand && data.command === bashCommand) {
        console.log(`[ToolUseBlock] Received confirmation request for block ${block.id}`)
        setCurrentConfirmationId(data.confirmation_id)
        setConfirmationStatus('pending')
      }
    }

    window.addEventListener('bashConfirmationRequest', handleBashConfirmationRequest as EventListener)

    return () => {
      window.removeEventListener('bashConfirmationRequest', handleBashConfirmationRequest as EventListener)
    }
  }, [isBashTool, bashCommand, block.id])

  // Keyboard navigation for pending confirmation
  useEffect(() => {
    if (confirmationStatus !== 'pending') return

    const handleKeyDown = (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowLeft':
        case 'ArrowUp':
          e.preventDefault()
          setSelectedButton('reject')
          break
        case 'ArrowRight':
        case 'ArrowDown':
          e.preventDefault()
          setSelectedButton('approve')
          break
        case 'Enter':
          e.preventDefault()
          if (selectedButton === 'approve') {
            handleApprove()
          } else {
            handleReject()
          }
          break
        case 'y':
        case 'Y':
          e.preventDefault()
          handleApprove()
          break
        case 'n':
        case 'N':
          e.preventDefault()
          handleReject()
          break
        case 'Escape':
          e.preventDefault()
          handleReject()
          break
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [confirmationStatus, selectedButton, handleApprove, handleReject])

  return (
    <div className="tool-use-block">
      <div className="tool-use-header">
        <span className="tool-use-prompt">$</span>
        <span className="tool-use-name">{block.name}</span>
        {hasInput && (
          <button
            className="tool-use-toggle"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse parameters' : 'Expand parameters'}
          >
            {isExpanded ? '−' : '+'}
          </button>
        )}
      </div>

      {/* Display bash command with interactive confirmation */}
      {isBashTool && bashCommand && (
        <div className="tool-use-bash-command">
          <div className="bash-command-label">Command:</div>
          <code className="bash-command-text">{bashCommand}</code>

          {confirmationStatus === 'pending' && (
            <div className="bash-confirmation-interactive">
              <button
                onClick={handleReject}
                onMouseEnter={() => setSelectedButton('reject')}
                className="bash-confirm-btn reject"
                style={{
                  color: selectedButton === 'reject' ? '#dc2626' : '#71717a',
                  fontWeight: selectedButton === 'reject' ? 600 : 400,
                  textDecoration: selectedButton === 'reject' ? 'underline' : 'none'
                }}
              >
                [n] reject
              </button>
              <button
                onClick={handleApprove}
                onMouseEnter={() => setSelectedButton('approve')}
                className="bash-confirm-btn approve"
                style={{
                  color: selectedButton === 'approve' ? '#059669' : '#71717a',
                  fontWeight: selectedButton === 'approve' ? 600 : 400,
                  textDecoration: selectedButton === 'approve' ? 'underline' : 'none'
                }}
              >
                [y] approve
              </button>
            </div>
          )}

          {confirmationStatus !== 'pending' && (
            <div className="bash-confirmation-status">
              <span className={`status-badge ${confirmationStatus}`}>
                {confirmationStatus === 'approved' ? '✓ Approved' : '✗ Rejected'}
              </span>
            </div>
          )}
        </div>
      )}

      {hasInput && isExpanded && (
        <div className="tool-use-input">
          <pre className="tool-use-input-content">
            {JSON.stringify(block.input, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export default ToolUseBlock
