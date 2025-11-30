import React, { useState, useEffect, useCallback } from 'react'
import { ToolUseBlock as ToolUseBlockType } from '@toyoura-nagisa/core'
import { useConnection } from '../../../contexts/connection/ConnectionContext'
import ToolDiffViewer from './ToolDiffViewer'
import ToolDiffViewerErrorBoundary from './ToolDiffViewerErrorBoundary'
import './ToolDiffBlock.css'

interface ToolDiffBlockProps {
  block: ToolUseBlockType
  messageId: string
}

type ConfirmationStatus = 'pending' | 'approved' | 'rejected'

/**
 * Tool diff block component for file operation tools (edit, write).
 *
 * Specialized component that displays file changes with git-style diff view
 * and handles user confirmation for file modifications. Separated from generic
 * ToolUseBlock for cleaner architecture and better maintainability.
 *
 * Key features:
 * - Git-style diff visualization via ToolDiffViewer
 * - Interactive confirmation UI for edit/write operations
 * - Keyboard navigation (y/n, arrows, Enter)
 * - No redundant headers or JSON parameter display
 *
 * Args:
 *     block: ToolUseBlock object with tool name and file operation parameters
 *     messageId: ID of the message containing this tool call
 *
 * Returns:
 *     JSX element with diff viewer and confirmation UI
 */
const ToolDiffBlock: React.FC<ToolDiffBlockProps> = ({ block, messageId }) => {
  const { pendingToolConfirmation, clearPendingToolConfirmation } = useConnection()

  const [confirmationStatus, setConfirmationStatus] = useState<ConfirmationStatus | null>(null)
  const [selectedButton, setSelectedButton] = useState<'reject' | 'approve'>('approve')

  /**
   * Send confirmation response to backend via WebSocket.
   */
  const sendConfirmationResponse = useCallback(async (approved: boolean, userMessage?: string) => {
    let ws = (window as any).__wsConnection

    if (!ws || ws.readyState !== WebSocket.OPEN) {
      const waitForConnection = (window as any).__waitForConnection
      if (waitForConnection) {
        const connected = await waitForConnection(3000)
        if (connected) {
          ws = (window as any).__wsConnection
        } else {
          console.error('[ToolDiffBlock] Failed to get WebSocket connection')
          return
        }
      }
    }

    if (ws && ws.readyState === WebSocket.OPEN) {
      const response = {
        type: 'TOOL_CONFIRMATION_RESPONSE',
        tool_call_id: block.id,
        approved,
        user_message: userMessage,
        timestamp: new Date().toISOString()
      }

      try {
        ws.send(JSON.stringify(response))
      } catch (error) {
        console.error('[ToolDiffBlock] Error sending tool confirmation response:', error)
      }
    }
  }, [block.id])

  /**
   * Handle user approval of the file operation.
   */
  const handleApprove = useCallback(() => {
    if (confirmationStatus === 'pending') {
      sendConfirmationResponse(true)
      setConfirmationStatus('approved')
    }
  }, [confirmationStatus, sendConfirmationResponse])

  /**
   * Handle user rejection of the file operation.
   */
  const handleReject = useCallback(() => {
    if (confirmationStatus === 'pending') {
      sendConfirmationResponse(false, 'File operation rejected by user')
      setConfirmationStatus('rejected')
    }
  }, [confirmationStatus, sendConfirmationResponse])

  /**
   * Listen for confirmation requests matching this tool block.
   */
  useEffect(() => {
    // Check for existing pending confirmation
    // Match by BOTH message_id AND tool_call_id (prevents conflicts with repeated tool_call_ids across messages)
    if (pendingToolConfirmation?.message_id === messageId &&
        pendingToolConfirmation?.tool_call_id === block.id) {
      setConfirmationStatus('pending')
      clearPendingToolConfirmation()
    }

    // Listen for new confirmation requests
    const handleToolConfirmationRequest = (event: CustomEvent) => {
      const data = event.detail
      // Match by BOTH message_id AND tool_call_id
      // This prevents conflicts when same tool_call_id appears in different messages (e.g., "bash:0")
      if (data.message_id === messageId && data.tool_call_id === block.id) {
        setConfirmationStatus('pending')
        clearPendingToolConfirmation()
      }
    }

    window.addEventListener('toolConfirmationRequest', handleToolConfirmationRequest as EventListener)

    return () => {
      window.removeEventListener('toolConfirmationRequest', handleToolConfirmationRequest as EventListener)
    }
  }, [messageId, block.id, pendingToolConfirmation, clearPendingToolConfirmation])

  /**
   * Keyboard navigation for confirmation UI.
   */
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
    <div className="tool-diff-block">
      {/* Core diff visualization */}
      <ToolDiffViewerErrorBoundary>
        <ToolDiffViewer
          toolName={block.name as 'edit' | 'write'}
          filePath={block.input?.file_path as string}
          oldString={block.input?.old_string as string | undefined}
          newString={block.input?.new_string as string | undefined}
          content={block.input?.content as string | undefined}
        />
      </ToolDiffViewerErrorBoundary>

      {/* Confirmation UI - matches bash tool style */}
      {confirmationStatus && (
        <div className="tool-use-bash-command">
          <div className="bash-command-label">
            {block.name === 'edit' ? 'Edit:' : 'Write:'}
          </div>
          <code className="bash-command-text">
            {block.input?.file_path as string}
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
    </div>
  )
}

export default ToolDiffBlock
