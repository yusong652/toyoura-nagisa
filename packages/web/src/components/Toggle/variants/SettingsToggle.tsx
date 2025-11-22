/**
 * Settings Toggle Component
 * 
 * Generic settings toggle placeholder that can be used for various settings.
 * Provides a flexible toggle component for future settings implementations.
 */

import React, { useState, useCallback } from 'react'
import { BaseToggle } from '../base/BaseToggle'

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
 * Generic settings toggle that can be used as a building block
 * for various settings throughout the application.
 * 
 * Supports both controlled and uncontrolled modes:
 * - Controlled: Pass `checked` prop to control state externally
 * - Uncontrolled: Pass `initialChecked` to set initial state, component manages state internally
 */
export const SettingsToggle: React.FC<SettingsToggleProps> = ({
  checked: controlledChecked,
  initialChecked = false,
  onChange,
  label,
  disabled = false,
  size = 'small',
  className = '',
  'data-testid': testId
}) => {
  // Use internal state only if not controlled
  const [internalChecked, setInternalChecked] = useState(initialChecked)
  
  // Determine if this is controlled or uncontrolled
  const isControlled = controlledChecked !== undefined
  const checked = isControlled ? controlledChecked : internalChecked

  const handleToggle = useCallback((newChecked: boolean) => {
    // Update internal state only if not controlled
    if (!isControlled) {
      setInternalChecked(newChecked)
    }
    
    // Always call onChange callback
    onChange?.(newChecked)
  }, [isControlled, onChange])

  return (
    <BaseToggle
      checked={checked}
      onChange={handleToggle}
      disabled={disabled}
      size={size}
      className={className}
      ariaLabel={label}
      data-testid={testId}
    />
  )
}