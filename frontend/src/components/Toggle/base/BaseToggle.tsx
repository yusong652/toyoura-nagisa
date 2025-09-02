/**
 * Base Toggle Component
 * 
 * Foundation toggle component based on the original SlideToggle design.
 * Provides core toggle functionality with accessibility support.
 */

import React, { useCallback } from 'react'
import type { BaseToggleProps } from '../types'
import './BaseToggle.css'

export const BaseToggle: React.FC<BaseToggleProps> = ({
  checked,
  onChange,
  disabled = false,
  size = 'small',
  className = '',
  ariaLabel,
  'data-testid': testId
}) => {
  const handleToggle = useCallback(() => {
    if (!disabled) {
      onChange(!checked)
    }
  }, [checked, onChange, disabled])

  const classNames = [
    'base-toggle',
    `base-toggle--${size}`,
    checked && 'base-toggle--checked',
    disabled && 'base-toggle--disabled',
    className
  ].filter(Boolean).join(' ')

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={handleToggle}
      disabled={disabled}
      className={classNames}
      data-testid={testId}
    >
      <span className="base-toggle__thumb" />
    </button>
  )
}

BaseToggle.displayName = 'BaseToggle'