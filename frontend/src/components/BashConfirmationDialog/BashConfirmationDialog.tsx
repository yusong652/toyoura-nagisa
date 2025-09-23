import React, { useState, useEffect, useRef } from 'react'
import { Chip } from '@mui/material'
import {
  ContentCopy as CopyIcon,
  Check as CheckIcon
} from '@mui/icons-material'
import { useBashConfirmation } from './hooks'
import './BashConfirmationDialog.css'

/**
 * Bash Command Confirmation Component
 *
 * Clean, minimal component for bash command confirmation within ChatBox.
 * Matches the design patterns of message and tool components.
 *
 * Features:
 * - Simple command display in code box
 * - Description from AI when provided
 * - Approve/reject actions
 * - 60-second auto-reject timeout
 * - Copy command functionality
 * - Keyboard navigation (arrows + enter)
 */
const BashConfirmationDialog: React.FC = () => {
  const { request, isOpen, approve, reject } = useBashConfirmation()
  const [timeRemaining, setTimeRemaining] = useState(60)
  const [copied, setCopied] = useState(false)
  const [selectedButton, setSelectedButton] = useState<'reject' | 'approve'>('approve')


  // Reset state when confirmation opens/closes
  useEffect(() => {
    if (isOpen) {
      setTimeRemaining(60)
      setCopied(false)
      setSelectedButton('approve') // Default to approve button
    }
  }, [isOpen])

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return

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
            reject('Command rejected by user via keyboard')
          }
          break
        case 'Escape':
          e.preventDefault()
          reject('Command cancelled by user')
          break
      }
    }

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown)
      return () => document.removeEventListener('keydown', handleKeyDown)
    }
  }, [isOpen, selectedButton, approve, reject])

  // Countdown timer
  useEffect(() => {
    if (isOpen && timeRemaining > 0) {
      const timer = setTimeout(() => {
        setTimeRemaining(prev => prev - 1)
      }, 1000)

      return () => clearTimeout(timer)
    }
  }, [isOpen, timeRemaining])

  // Copy command to clipboard
  const handleCopy = () => {
    if (request?.command) {
      navigator.clipboard.writeText(request.command)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  // Handle approve
  const handleApprove = () => {
    approve()
  }

  // Handle reject - simplified to just reject immediately
  const handleReject = () => {
    reject('Command rejected by user')
  }

  if (!request || !isOpen) {
    return null
  }

  return (
    <div className="bash-confirmation-container">
      {/* Compact content */}
      <div className="bash-confirmation-content">
        {/* Code display box with copy button - most important info */}
        <div className="bash-confirmation-code-box">
          <button
            className="bash-confirmation-copy-button"
            onClick={handleCopy}
          >
            {copied ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
          </button>
          <pre className="bash-confirmation-command">
            {request.command}
          </pre>
        </div>
      </div>

      {/* Compact actions with timeout */}
      <div className="bash-confirmation-actions">
        <div className="bash-confirmation-timeout-inline">
          <Chip
            label={`${timeRemaining}s`}
            size="small"
            color={timeRemaining > 10 ? 'default' : 'error'}
            className="bash-confirmation-timeout-chip"
          />
        </div>
        <div className="bash-confirmation-buttons">
          <button
            onClick={handleReject}
            className={`bash-confirmation-button bash-confirmation-reject ${selectedButton === 'reject' ? 'selected' : ''}`}
          >
            Reject
          </button>
          <button
            onClick={handleApprove}
            className={`bash-confirmation-button bash-confirmation-approve ${selectedButton === 'approve' ? 'selected' : ''}`}
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  )
}

export default BashConfirmationDialog