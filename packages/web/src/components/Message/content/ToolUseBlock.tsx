import React, { useState, useEffect, useCallback, useRef } from 'react'
import { ToolUseBlock as ToolUseBlockType } from '../../../types/chat'
import { useConnection } from '../../../contexts/connection/ConnectionContext'

interface ToolUseBlockProps {
  block: ToolUseBlockType
  messageId: string
}

type ConfirmationStatus = 'pending' | 'approved' | 'rejected'

/**
 * Tool use block component for displaying tool calls.
 *
 * Shows the tool name, input parameters in a collapsible format.
 * For tools requiring confirmation (configured in backend), displays interactive confirmation UI inline.
 * Supports multiple tool calls in a single message.
 *
 * Args:
 *     block: ToolUseBlock object with tool name and input parameters
 *
 * Returns:
 *     JSX element with tool call display
 */
const ToolUseBlock: React.FC<ToolUseBlockProps> = ({ block, messageId }) => {
  // Use Connection Context for tool confirmation management
  const { pendingToolConfirmation, clearPendingToolConfirmation } = useConnection()

  const [isExpanded, setIsExpanded] = useState(false)
  const [confirmationStatus, setConfirmationStatus] = useState<ConfirmationStatus | null>(null) // null = no confirmation UI, will be set to pending when request arrives
  const [selectedButton, setSelectedButton] = useState<'reject' | 'approve'>('approve')

  const blockIdRef = useRef(block.id)

  const hasInput = block.input && Object.keys(block.input).length > 0

  // Send confirmation response via WebSocket
  const sendConfirmationResponse = useCallback(async (approved: boolean, userMessage?: string) => {
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
        type: 'TOOL_CONFIRMATION_RESPONSE',
        tool_call_id: block.id,  // Use block.id as tool_call_id
        approved,
        user_message: userMessage,
        timestamp: new Date().toISOString()
      }

      try {
        ws.send(JSON.stringify(response))
      } catch (error) {
        console.error('[ToolUseBlock] Error sending tool confirmation response:', error)
      }
    }
  }, [block.id])

  // Handle approval
  const handleApprove = useCallback(() => {
    if (confirmationStatus === 'pending') {
      sendConfirmationResponse(true)
      setConfirmationStatus('approved')
    }
  }, [confirmationStatus, sendConfirmationResponse])

  // Handle rejection
  const handleReject = useCallback(() => {
    if (confirmationStatus === 'pending') {
      sendConfirmationResponse(false, 'Command rejected by user')
      setConfirmationStatus('rejected')
    }
  }, [confirmationStatus, sendConfirmationResponse])

  // Check for pending confirmation on mount and listen for new requests
  useEffect(() => {
    // Check if there's a pending confirmation that matches this tool block
    // Using React Context instead of window global variables
    if (pendingToolConfirmation) {
      // Match by BOTH message_id AND tool_call_id (prevents conflicts with repeated tool_call_ids across messages)
      if (pendingToolConfirmation.message_id === messageId &&
          pendingToolConfirmation.tool_call_id === block.id) {
        setConfirmationStatus('pending')
        // Clear the pending confirmation since we've consumed it
        clearPendingToolConfirmation()
      }
    }

    // Also listen for new confirmation requests via event
    const handleToolConfirmationRequest = (event: CustomEvent) => {
      const data = event.detail

      // Match this confirmation request to this tool block by BOTH message_id AND tool_call_id
      // This prevents conflicts when same tool_call_id appears in different messages (e.g., "bash:0")
      if (data.message_id === messageId && data.tool_call_id === block.id) {
        setConfirmationStatus('pending')
        // Clear the pending confirmation since we've consumed it
        clearPendingToolConfirmation()
      }
    }

    window.addEventListener('toolConfirmationRequest', handleToolConfirmationRequest as EventListener)

    return () => {
      window.removeEventListener('toolConfirmationRequest', handleToolConfirmationRequest as EventListener)
    }
  }, [messageId, block.id, pendingToolConfirmation, clearPendingToolConfirmation])

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

      {/* Display tool operation with interactive confirmation (for tools requiring confirmation) */}
      {confirmationStatus && (
        <div className="tool-use-bash-command">
          <div className="bash-command-label">
            {block.name === 'bash' ? 'Command:' :
             block.name === 'edit' ? 'Edit:' :
             block.name === 'write' ? 'Write:' :
             block.name === 'pfc_execute_script' ? 'PFC Script:' : 'Operation:'}
          </div>
          <code className="bash-command-text">
            {block.name === 'bash' && block.input?.command ? block.input.command as string :
             block.name === 'edit' && block.input?.file_path ? `${block.input.file_path}` :
             block.name === 'write' && block.input?.file_path ? `${block.input.file_path}` :
             block.name === 'pfc_execute_script' && block.input?.script_path ?
               `${block.input.script_path}${block.input?.run_in_background ? ' (background)' : ' (foreground)'}` :
             'Unknown operation'}
          </code>

          {/* Show interactive buttons when pending confirmation */}
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

          {/* Show status badge after confirmation (approved/rejected) */}
          {confirmationStatus !== null && confirmationStatus !== 'pending' && (
            <div className="bash-confirmation-status">
              <span className={`status-badge ${confirmationStatus}`}>
                {confirmationStatus === 'approved' ? '✓ Approved' : '✗ Rejected'}
              </span>
            </div>
          )}
        </div>
      )}

      {/* Show raw JSON parameters */}
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
