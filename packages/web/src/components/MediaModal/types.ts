import { ReactNode } from 'react'

/**
 * MediaModal TypeScript type definitions.
 * 
 * Comprehensive type system for media modal components (Image, Video, etc.),
 * following aiNagisa's clean architecture principles with shared modal behavior.
 */

// =============================================================================
// Core Component Types
// =============================================================================

export interface MediaModalProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  className?: string
  title?: string
  showCloseButton?: boolean
  preventBackgroundClose?: boolean
  preventEscapeClose?: boolean
}

export interface MediaModalHeaderProps {
  title?: string
  subtitle?: string
  onClose: () => void
  showCloseButton?: boolean
  className?: string
}

export interface MediaModalContainerProps {
  children: ReactNode
  className?: string
  onClick?: (e: React.MouseEvent) => void
}

// =============================================================================
// Hook Return Types
// =============================================================================

export interface UseMediaModalReturn {
  handleBackgroundClick: (e: React.MouseEvent) => void
  handleContainerClick: (e: React.MouseEvent) => void
  isClosing: boolean
}

export interface UseKeyboardShortcutsOptions {
  onClose?: () => void
  onNext?: () => void
  onPrevious?: () => void
  onZoomIn?: () => void
  onZoomOut?: () => void
  onZoomReset?: () => void
  customHandlers?: Record<string, (e: KeyboardEvent) => void>
  disabled?: boolean
}

export interface UsePreventBodyScrollOptions {
  enabled: boolean
  restoreOnUnmount?: boolean
}

// =============================================================================
// Media Types
// =============================================================================

export type MediaType = 'image' | 'video' | 'audio' | 'document'

export interface MediaInfo {
  url: string
  name?: string
  type?: MediaType
  format?: string
  thumbnail?: string
}

// =============================================================================
// Navigation Types
// =============================================================================

export interface MediaNavigationProps {
  currentIndex: number
  totalItems: number
  onNext: () => void
  onPrevious: () => void
  canNavigate?: boolean
  className?: string
}

// =============================================================================
// Control Types
// =============================================================================

export interface MediaControlsProps {
  children?: ReactNode
  className?: string
  position?: 'top' | 'bottom' | 'left' | 'right' | 'center'
}

// =============================================================================
// Loading States
// =============================================================================

export interface MediaLoadingProps {
  message?: string
  showSpinner?: boolean
  className?: string
}

// =============================================================================
// Error States
// =============================================================================

export interface MediaErrorProps {
  error?: string | Error
  onRetry?: () => void
  className?: string
}

// =============================================================================
// Animation States
// =============================================================================

export interface AnimationState {
  isEntering: boolean
  isLeaving: boolean
  animationDuration: number
}

// =============================================================================
// Utility Types
// =============================================================================

export type CloseReason = 'escape' | 'background-click' | 'close-button' | 'programmatic'

export interface CloseEvent {
  reason: CloseReason
  preventDefault: () => void
}

// =============================================================================
// Constants
// =============================================================================

export const ANIMATION_DURATION = 200 // milliseconds

export const KEYBOARD_SHORTCUTS = {
  CLOSE: 'Escape',
  NEXT: 'ArrowRight',
  PREVIOUS: 'ArrowLeft',
  ZOOM_IN: '+',
  ZOOM_OUT: '-',
  ZOOM_RESET: '0',
} as const

// =============================================================================
// Type Guards
// =============================================================================

export const isMediaInfo = (obj: any): obj is MediaInfo => {
  return obj && typeof obj.url === 'string'
}

export const isValidMediaType = (type: any): type is MediaType => {
  return ['image', 'video', 'audio', 'document'].includes(type)
}