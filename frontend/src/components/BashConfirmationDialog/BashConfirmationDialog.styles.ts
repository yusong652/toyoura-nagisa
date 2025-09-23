/**
 * Styles for BashConfirmationDialog component
 *
 * Theme-aware styling supporting both dark and light modes
 * Detects theme using data-theme attribute on body
 */

import { SxProps, Theme } from '@mui/material'

export const dialogStyles = {
  // Dialog paper - unified with tool state theme
  paper: (isDarkMode: boolean) => ({
    borderRadius: '16px',
    maxWidth: '600px',
    backgroundColor: isDarkMode ? 'rgba(26, 26, 26, 0.95)' : 'rgba(255, 255, 255, 0.98)',
    backgroundImage: isDarkMode
      ? 'linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(37, 99, 235, 0.02) 100%)'
      : 'linear-gradient(135deg, rgba(59, 130, 246, 0.03) 0%, rgba(37, 99, 235, 0.01) 100%)',
    border: '1px solid',
    borderColor: isDarkMode
      ? 'rgba(59, 130, 246, 0.2)'
      : 'rgba(59, 130, 246, 0.15)',
    color: isDarkMode ? '#e8e8e8' : '#333333',
    backdropFilter: 'blur(20px) saturate(150%)',
    WebkitBackdropFilter: 'blur(20px) saturate(150%)',
    boxShadow: isDarkMode
      ? '0 4px 20px rgba(59, 130, 246, 0.12), 0 1px 3px rgba(0, 0, 0, 0.3)'
      : '0 4px 20px rgba(59, 130, 246, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05)'
  }) as SxProps<Theme>,

  // Dialog title - matching tool state style
  dialogTitle: (isDarkMode: boolean) => ({
    pb: 2,
    pt: 2.5,
    fontSize: '1rem',
    fontWeight: 600,
    letterSpacing: '0.3px',
    color: isDarkMode ? '#d4d4d8' : '#52525b',
    fontFamily: '"SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", "Roboto", sans-serif'
  }) as SxProps<Theme>,

  // Content container
  dialogContent: {
    pt: 0,
    pb: 2
  } as SxProps<Theme>,

  // Description text - matching tool state thinking text
  descriptionText: (isDarkMode: boolean) => ({
    color: isDarkMode ? '#a1a1aa' : '#71717a',
    mb: 2,
    fontSize: '0.95rem',
    letterSpacing: '0.2px',
    fontFamily: '"SF Pro Display", -apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", "Roboto", sans-serif',
    lineHeight: 1.5
  }) as SxProps<Theme>,

  // Code display box - unified with tool state viewport style
  codeBox: (isDarkMode: boolean) => ({
    backgroundColor: isDarkMode
      ? 'rgba(0, 0, 0, 0.4)'
      : 'rgba(0, 0, 0, 0.03)',
    backgroundImage: isDarkMode
      ? 'linear-gradient(135deg, rgba(0, 0, 0, 0.03) 0%, rgba(0, 0, 0, 0.01) 100%)'
      : 'linear-gradient(135deg, rgba(0, 0, 0, 0.03) 0%, rgba(0, 0, 0, 0.01) 100%)',
    color: isDarkMode ? '#d4d4d4' : '#374151',
    borderRadius: '12px',
    p: 2,
    fontFamily: 'monospace',
    fontSize: '0.9rem',
    overflowX: 'auto',
    border: '1px solid',
    borderColor: isDarkMode
      ? 'rgba(255, 255, 255, 0.08)'
      : 'rgba(255, 255, 255, 0.08)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    mb: 2,
    position: 'relative'
  }) as SxProps<Theme>,

  // Command text inside code box
  commandText: {
    margin: 0,
    fontFamily: 'monospace',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    lineHeight: 1.5,
    color: 'inherit' // Inherit from parent codeBox
  } as SxProps<Theme>,

  // Copy button in code box
  copyButton: (isDarkMode: boolean) => ({
    position: 'absolute',
    top: 8,
    right: 8,
    minWidth: 'auto',
    p: 0.5,
    color: 'text.secondary',
    '&:hover': {
      color: 'text.primary',
      backgroundColor: isDarkMode ? 'rgba(255, 255, 255, 0.08)' : 'rgba(0, 0, 0, 0.08)'
    }
  }) as SxProps<Theme>,

  // Info text - subtle and clean
  infoText: (isDarkMode: boolean) => ({
    color: isDarkMode ? '#a1a1aa' : '#71717a',
    fontSize: '0.85rem',
    mb: 1.5,
    opacity: 0.9,
    letterSpacing: '0.2px'
  }) as SxProps<Theme>,

  // Timeout chip - matching tool state theme
  timeoutChip: (isDarkMode: boolean) => ({
    fontSize: '0.75rem',
    height: 24,
    borderColor: 'rgba(59, 130, 246, 0.2)',
    backgroundColor: isDarkMode
      ? 'rgba(59, 130, 246, 0.1)'
      : 'rgba(59, 130, 246, 0.08)',
    color: isDarkMode ? '#93c5fd' : '#3b82f6',
    fontWeight: 500
  }) as SxProps<Theme>,

  // Dialog actions - clean layout
  dialogActions: (isDarkMode: boolean) => ({
    p: 2,
    pt: 0,
    gap: 1,
    display: 'flex',
    justifyContent: 'flex-end',
    borderTop: '1px solid',
    borderColor: isDarkMode ? 'rgba(255, 255, 255, 0.12)' : 'rgba(0, 0, 0, 0.12)'
  }) as SxProps<Theme>,

  // Reject button - subtle styling
  rejectButton: (isDarkMode: boolean) => ({
    color: isDarkMode ? '#a1a1aa' : '#71717a',
    fontWeight: 500,
    '&:hover': {
      backgroundColor: isDarkMode
        ? 'rgba(255, 255, 255, 0.08)'
        : 'rgba(0, 0, 0, 0.04)',
      color: isDarkMode ? '#d4d4d8' : '#52525b'
    }
  }) as SxProps<Theme>,

  // Approve button - blue theme matching tool state
  approveButton: (isDarkMode: boolean) => ({
    background: isDarkMode
      ? 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)'
      : 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
    color: '#ffffff',
    fontWeight: 500,
    boxShadow: '0 2px 8px rgba(59, 130, 246, 0.3)',
    '&:hover': {
      background: isDarkMode
        ? 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)'
        : 'linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%)',
      boxShadow: '0 4px 12px rgba(59, 130, 246, 0.4)'
    }
  }) as SxProps<Theme>
}