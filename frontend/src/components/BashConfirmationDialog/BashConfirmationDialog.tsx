import React, { useState, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  TextField,
  Box,
  Alert,
  Chip,
  LinearProgress,
  IconButton
} from '@mui/material'
import {
  Terminal as TerminalIcon,
  Warning as WarningIcon,
  ContentCopy as CopyIcon,
  Check as CheckIcon
} from '@mui/icons-material'
import useBashConfirmation from '../../hooks/useBashConfirmation'

/**
 * Bash Command Confirmation Dialog Component
 *
 * Displays a confirmation dialog when the AI wants to execute a bash command,
 * following Claude Code's user-in-the-loop design pattern.
 *
 * Features:
 * - Clear command display with syntax highlighting
 * - Optional command description from AI
 * - User can provide rejection reason
 * - 60-second auto-reject timeout
 * - Copy command to clipboard functionality
 * - Visual security warnings
 *
 * Design:
 * - Material-UI dialog with warning theme
 * - Terminal-style command display
 * - Clear approve/reject actions
 * - Optional user message input when rejecting
 */
const BashConfirmationDialog: React.FC = () => {
  const { request, isOpen, approve, reject } = useBashConfirmation()
  const [userMessage, setUserMessage] = useState('')
  const [showRejectInput, setShowRejectInput] = useState(false)
  const [timeRemaining, setTimeRemaining] = useState(60)
  const [copied, setCopied] = useState(false)

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (isOpen) {
      setUserMessage('')
      setShowRejectInput(false)
      setTimeRemaining(60)
      setCopied(false)
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

  // Handle reject
  const handleReject = () => {
    if (showRejectInput) {
      reject(userMessage || undefined)
    } else {
      setShowRejectInput(true)
    }
  }

  // Cancel reject input
  const handleCancelReject = () => {
    setShowRejectInput(false)
    setUserMessage('')
  }

  if (!request) {
    return null
  }

  return (
    <Dialog
      open={isOpen}
      onClose={() => reject('Dialog closed by user')}
      maxWidth="md"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 2,
          border: '2px solid',
          borderColor: 'warning.main'
        }
      }}
    >
      {/* Header */}
      <DialogTitle sx={{ pb: 1 }}>
        <Box display="flex" alignItems="center" gap={1}>
          <WarningIcon color="warning" />
          <Typography variant="h6" component="span">
            Bash Command Confirmation Required
          </Typography>
        </Box>
      </DialogTitle>

      {/* Progress bar for timeout */}
      <LinearProgress
        variant="determinate"
        value={(timeRemaining / 60) * 100}
        sx={{
          height: 3,
          backgroundColor: 'action.disabledBackground',
          '& .MuiLinearProgress-bar': {
            backgroundColor: timeRemaining > 10 ? 'warning.main' : 'error.main'
          }
        }}
      />

      {/* Content */}
      <DialogContent sx={{ pt: 2 }}>
        {/* Security Warning */}
        <Alert severity="warning" sx={{ mb: 2 }}>
          <Typography variant="body2">
            The AI assistant wants to execute a bash command. Please review it carefully
            before approving. This command will run on your system.
          </Typography>
        </Alert>

        {/* Command Description */}
        {request.description && (
          <Box mb={2}>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              AI's Description:
            </Typography>
            <Typography variant="body1">{request.description}</Typography>
          </Box>
        )}

        {/* Command Display */}
        <Box mb={2}>
          <Box display="flex" alignItems="center" justifyContent="space-between" mb={1}>
            <Typography variant="subtitle2" color="text.secondary">
              Command to Execute:
            </Typography>
            <IconButton
              size="small"
              onClick={handleCopy}
              color={copied ? 'success' : 'default'}
            >
              {copied ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
            </IconButton>
          </Box>

          <Box
            sx={{
              backgroundColor: '#1e1e1e',
              color: '#d4d4d4',
              p: 2,
              borderRadius: 1,
              fontFamily: 'monospace',
              fontSize: '0.9rem',
              position: 'relative',
              overflowX: 'auto'
            }}
          >
            <Box display="flex" alignItems="center" gap={1} mb={1}>
              <TerminalIcon sx={{ fontSize: '1rem', color: '#4ec9b0' }} />
              <Typography
                component="span"
                sx={{ color: '#4ec9b0', fontFamily: 'monospace', fontSize: '0.8rem' }}
              >
                bash
              </Typography>
            </Box>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
              {request.command}
            </pre>
          </Box>
        </Box>

        {/* Rejection Input */}
        {showRejectInput && (
          <Box>
            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
              Rejection Reason (optional):
            </Typography>
            <TextField
              fullWidth
              multiline
              rows={3}
              value={userMessage}
              onChange={(e) => setUserMessage(e.target.value)}
              placeholder="Provide feedback to help the AI understand why you're rejecting this command..."
              variant="outlined"
              autoFocus
              sx={{ mb: 1 }}
            />
          </Box>
        )}

        {/* Timeout Warning */}
        <Box display="flex" alignItems="center" justifyContent="space-between" mt={2}>
          <Chip
            label={`Auto-reject in ${timeRemaining}s`}
            size="small"
            color={timeRemaining > 10 ? 'default' : 'error'}
            variant="outlined"
          />
        </Box>
      </DialogContent>

      {/* Actions */}
      <DialogActions sx={{ p: 2, pt: 0 }}>
        {showRejectInput ? (
          <>
            <Button onClick={handleCancelReject} color="inherit">
              Cancel
            </Button>
            <Button onClick={handleReject} color="error" variant="contained">
              Send Rejection
            </Button>
          </>
        ) : (
          <>
            <Button onClick={handleReject} color="error">
              Reject
            </Button>
            <Button onClick={handleApprove} variant="contained" color="success">
              Approve & Execute
            </Button>
          </>
        )}
      </DialogActions>
    </Dialog>
  )
}

export default BashConfirmationDialog