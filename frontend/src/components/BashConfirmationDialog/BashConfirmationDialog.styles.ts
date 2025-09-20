/**
 * Styles for BashConfirmationDialog component
 *
 * Centralized Material-UI sx styles for better maintainability
 */

import { SxProps, Theme } from '@mui/material'

export const dialogStyles = {
  paper: {
    borderRadius: 2,
    border: '2px solid',
    borderColor: 'warning.main'
  } as SxProps<Theme>,

  dialogTitle: {
    pb: 1
  } as SxProps<Theme>,

  progressBar: {
    height: 3,
    backgroundColor: 'action.disabledBackground'
  } as SxProps<Theme>,

  progressBarColor: (timeRemaining: number) => ({
    '& .MuiLinearProgress-bar': {
      backgroundColor: timeRemaining > 10 ? 'warning.main' : 'error.main'
    }
  } as SxProps<Theme>),

  dialogContent: {
    pt: 2
  } as SxProps<Theme>,

  warningAlert: {
    mb: 2
  } as SxProps<Theme>,

  descriptionBox: {
    mb: 2
  } as SxProps<Theme>,

  commandSection: {
    mb: 2
  } as SxProps<Theme>,

  commandHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    mb: 1
  } as SxProps<Theme>,

  terminalBox: {
    backgroundColor: '#1e1e1e',
    color: '#d4d4d4',
    p: 2,
    borderRadius: 1,
    fontFamily: 'monospace',
    fontSize: '0.9rem',
    position: 'relative',
    overflowX: 'auto'
  } as SxProps<Theme>,

  terminalHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 1,
    mb: 1
  } as SxProps<Theme>,

  terminalIcon: {
    fontSize: '1rem',
    color: '#4ec9b0'
  } as SxProps<Theme>,

  terminalLabel: {
    color: '#4ec9b0',
    fontFamily: 'monospace',
    fontSize: '0.8rem'
  } as SxProps<Theme>,

  commandText: {
    margin: 0,
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all'
  } as SxProps<Theme>,

  rejectInputSection: {
    mb: 2
  } as SxProps<Theme>,

  rejectTextField: {
    '& .MuiOutlinedInput-root': {
      fontFamily: 'inherit'
    }
  } as SxProps<Theme>,

  timerBox: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 1
  } as SxProps<Theme>,

  dialogActions: {
    px: 3,
    pb: 2
  } as SxProps<Theme>,

  // Button styles
  approveButton: {
    backgroundColor: 'success.main',
    '&:hover': {
      backgroundColor: 'success.dark'
    }
  } as SxProps<Theme>,

  rejectButton: {
    backgroundColor: 'error.main',
    '&:hover': {
      backgroundColor: 'error.dark'
    }
  } as SxProps<Theme>,

  cancelButton: {
    // Uses default button styling
  } as SxProps<Theme>
}

// Helper function to combine multiple sx props
export const combineSx = (...styles: (SxProps<Theme> | undefined)[]): SxProps<Theme> => {
  const filtered = styles.filter(Boolean) as SxProps<Theme>[]
  return filtered.reduce((acc, style) => ({
    ...acc,
    ...(style as any)
  }), {} as SxProps<Theme>)
}