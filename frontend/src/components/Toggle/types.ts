/**
 * Toggle Component Type Definitions
 * 
 * Comprehensive type system for Toggle components following the Message module pattern.
 * Provides base interfaces and specific toggle variant types.
 */

import { ReactNode } from 'react'

/**
 * Base Toggle component props
 */
export interface BaseToggleProps {
  /** Current toggle state */
  checked: boolean
  
  /** Callback when toggle state changes */
  onChange: (checked: boolean) => void
  
  /** Whether the toggle is disabled */
  disabled?: boolean
  
  /** Toggle size variant */
  size?: 'small' | 'medium' | 'large'
  
  /** Additional CSS classes */
  className?: string
  
  /** Accessible label for screen readers */
  ariaLabel?: string
  
  /** Test ID for testing */
  'data-testid'?: string
}

/**
 * Theme Toggle specific props
 */
export interface ThemeToggleProps {
  /** Optional callback when theme changes */
  onThemeChange?: (theme: 'light' | 'dark') => void
  
  /** Additional CSS classes */
  className?: string
}

/**
 * TTS Toggle specific props
 */
export interface TTSToggleProps {
  /** Initial TTS enabled state */
  initialEnabled?: boolean
  
  /** Callback when TTS state changes */
  onTTSChange?: (enabled: boolean) => void
  
  /** Additional CSS classes */
  className?: string
}

/**
 * Live2D Toggle specific props
 */
export interface Live2DToggleProps {
  /** Initial Live2D display state */
  initialDisplay?: boolean
  
  /** Callback when Live2D display changes */
  onDisplayChange?: (display: boolean) => void
  
  /** Additional CSS classes */
  className?: string
}

/**
 * Settings Toggle specific props
 * Supports both controlled and uncontrolled modes
 */
export interface SettingsToggleProps {
  /** Controlled toggle state */
  checked?: boolean
  
  /** Initial toggle state (used when not controlled) */
  initialChecked?: boolean
  
  /** Callback when toggle state changes */
  onChange?: (checked: boolean) => void
  
  /** Toggle label for accessibility */
  label?: string
  
  /** Whether the toggle is disabled */
  disabled?: boolean
  
  /** Toggle size */
  size?: 'small' | 'medium' | 'large'
  
  /** Additional CSS classes */
  className?: string
  
  /** Test ID for testing */
  'data-testid'?: string
}

/**
 * Toggle state for useToggle hook
 */
export interface ToggleState {
  checked: boolean
  disabled: boolean
}

/**
 * Toggle actions for useToggle hook
 */
export interface ToggleActions {
  toggle: () => void
  setChecked: (checked: boolean) => void
  setDisabled: (disabled: boolean) => void
}

/**
 * useToggle hook return type
 */
export interface UseToggleReturn {
  state: ToggleState
  actions: ToggleActions
}