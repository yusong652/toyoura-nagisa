import React, { useState, useEffect } from 'react'
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Typography,
  Box,
  Chip,
  IconButton
} from '@mui/material'
import {
  ContentCopy as CopyIcon,
  Check as CheckIcon
} from '@mui/icons-material'
import { useBashConfirmation } from './hooks'
import { dialogStyles } from './BashConfirmationDialog.styles'

/**
 * Bash Command Confirmation Dialog Component
 *
 * Clean, minimal dialog for bash command confirmation.
 * Matches the design patterns of message and tool components.
 *
 * Features:
 * - Simple command display in code box
 * - Description from AI when provided
 * - Approve/reject actions
 * - 60-second auto-reject timeout
 * - Copy command functionality
 */
const BashConfirmationDialog: React.FC = () => {
  const { request, isOpen, approve, reject } = useBashConfirmation()
  const [timeRemaining, setTimeRemaining] = useState(60)
  const [copied, setCopied] = useState(false)
  const [isDarkMode, setIsDarkMode] = useState(false)

  // Detect theme from body's data-theme attribute
  useEffect(() => {
    const checkTheme = () => {
      const theme = document.body.getAttribute('data-theme')
      setIsDarkMode(theme === 'dark')
    }

    checkTheme()

    // Observe theme changes
    const observer = new MutationObserver(checkTheme)
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['data-theme']
    })

    return () => observer.disconnect()
  }, [])

  // Reset state when dialog opens/closes
  useEffect(() => {
    if (isOpen) {
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

  // Handle reject - simplified to just reject immediately
  const handleReject = () => {
    reject('Command rejected by user')
  }

  if (!request) {
    return null
  }

  return (
    <Dialog
      open={isOpen}
      onClose={() => reject('Dialog closed by user')}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: dialogStyles.paper(isDarkMode)
      }}
    >
      {/* Simple title */}
      <DialogTitle sx={dialogStyles.dialogTitle(isDarkMode)}>
        Confirm Bash Command
      </DialogTitle>

      {/* Content */}
      <DialogContent sx={dialogStyles.dialogContent}>
        {/* AI Description if provided */}
        {request.description && (
          <Typography sx={dialogStyles.descriptionText(isDarkMode)}>
            {request.description}
          </Typography>
        )}

        {/* Code display box with copy button */}
        <Box sx={dialogStyles.codeBox(isDarkMode)}>
          <IconButton
            size="small"
            onClick={handleCopy}
            sx={dialogStyles.copyButton(isDarkMode)}
          >
            {copied ? <CheckIcon fontSize="small" /> : <CopyIcon fontSize="small" />}
          </IconButton>
          <Typography component="pre" sx={dialogStyles.commandText}>
            {request.command}
          </Typography>
        </Box>

        {/* Simple info text */}
        <Typography sx={dialogStyles.infoText(isDarkMode)}>
          This command will run on your system. You can provide feedback through chat if you reject.
        </Typography>

        {/* Timeout indicator */}
        <Box display="flex" justifyContent="center">
          <Chip
            label={`Auto-reject in ${timeRemaining}s`}
            size="small"
            color={timeRemaining > 10 ? 'default' : 'error'}
            sx={dialogStyles.timeoutChip(isDarkMode)}
          />
        </Box>
      </DialogContent>

      {/* Actions */}
      <DialogActions sx={dialogStyles.dialogActions(isDarkMode)}>
        <Button
          onClick={handleReject}
          sx={dialogStyles.rejectButton(isDarkMode)}
        >
          Reject
        </Button>
        <Button
          onClick={handleApprove}
          variant="contained"
          sx={dialogStyles.approveButton(isDarkMode)}
        >
          Approve
        </Button>
      </DialogActions>
    </Dialog>
  )
}

export default BashConfirmationDialog