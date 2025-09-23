/**
 * Styles for BashConfirmationDialog component
 *
 * Simplified styles for the streamlined confirmation dialog
 */

import { SxProps, Theme } from '@mui/material'

export const dialogStyles = {
  paper: {
    borderRadius: 2,
    border: '2px solid',
    borderColor: 'warning.main'
  } as SxProps<Theme>,

  commandText: {
    margin: 0,
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-all'
  } as SxProps<Theme>
}