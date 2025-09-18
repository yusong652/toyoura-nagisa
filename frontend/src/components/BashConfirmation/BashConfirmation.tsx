import React, { useState, useEffect } from 'react'
import './BashConfirmation.css'
import useBashConfirmation from '../../hooks/useBashConfirmation'

/**
 * Bash Command Confirmation Component
 *
 * A modal dialog that appears when the AI wants to execute a bash command.
 * Following Claude Code's user-in-the-loop design pattern.
 *
 * Features:
 * - Clear command display
 * - Optional command description
 * - User rejection message support
 * - 60-second auto-reject timeout
 * - Clean, focused UI design
 */
const BashConfirmation: React.FC = () => {
  const { request, isOpen, approve, reject } = useBashConfirmation()
  const [userMessage, setUserMessage] = useState('')
  const [showRejectInput, setShowRejectInput] = useState(false)
  const [timeRemaining, setTimeRemaining] = useState(60)

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (isOpen) {
      setUserMessage('')
      setShowRejectInput(false)
      setTimeRemaining(60)
    }
  }, [isOpen])

  // Countdown timer
  useEffect(() => {
    if (isOpen && timeRemaining > 0) {
      const timer = setTimeout(() => {
        setTimeRemaining(prev => prev - 1)
      }, 1000)

      return () => clearTimeout(timer)
    }
  }, [isOpen, timeRemaining])

  const handleApprove = () => {
    approve()
  }

  const handleReject = () => {
    if (showRejectInput) {
      reject(userMessage || undefined)
    } else {
      setShowRejectInput(true)
    }
  }

  const handleCancelReject = () => {
    setShowRejectInput(false)
    setUserMessage('')
  }

  const handleClose = () => {
    reject('Dialog closed by user')
  }

  if (!isOpen || !request) {
    return null
  }

  return (
    <div className="bash-confirmation-overlay" onClick={handleClose}>
      <div className="bash-confirmation-dialog" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="bash-confirmation-header">
          <h3>⚠️ Bash Command Confirmation</h3>
          <button className="close-button" onClick={handleClose}>×</button>
        </div>

        {/* Progress bar */}
        <div className="bash-confirmation-progress">
          <div
            className="progress-bar"
            style={{
              width: `${(timeRemaining / 60) * 100}%`,
              backgroundColor: timeRemaining > 10 ? '#ff9800' : '#f44336'
            }}
          />
        </div>

        {/* Content */}
        <div className="bash-confirmation-content">
          {/* Warning */}
          <div className="warning-box">
            <p>The AI wants to execute a bash command. Review it carefully before approving.</p>
          </div>

          {/* Description */}
          {request.description && (
            <div className="description-section">
              <label>AI's Description:</label>
              <p>{request.description}</p>
            </div>
          )}

          {/* Command */}
          <div className="command-section">
            <label>Command to Execute:</label>
            <div className="command-box">
              <pre>{request.command}</pre>
            </div>
          </div>

          {/* Rejection Input */}
          {showRejectInput && (
            <div className="reject-input-section">
              <label>Rejection Reason (optional):</label>
              <textarea
                value={userMessage}
                onChange={(e) => setUserMessage(e.target.value)}
                placeholder="Tell the AI why you're rejecting this command..."
                rows={3}
                autoFocus
              />
            </div>
          )}

          {/* Timer */}
          <div className="timer-section">
            <span className="timer-label">Auto-reject in {timeRemaining}s</span>
          </div>
        </div>

        {/* Actions */}
        <div className="bash-confirmation-actions">
          {showRejectInput ? (
            <>
              <button className="button button-cancel" onClick={handleCancelReject}>
                Cancel
              </button>
              <button className="button button-reject" onClick={handleReject}>
                Send Rejection
              </button>
            </>
          ) : (
            <>
              <button className="button button-reject" onClick={handleReject}>
                Reject
              </button>
              <button className="button button-approve" onClick={handleApprove}>
                Approve & Execute
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default BashConfirmation