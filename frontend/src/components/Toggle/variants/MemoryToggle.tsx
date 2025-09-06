/**
 * Memory Toggle Component
 * 
 * Toggle for enabling/disabling memory injection in AI responses.
 * When enabled, the AI will have access to relevant conversation history
 * and context from previous interactions.
 */

import React, { useCallback } from 'react'
import { useMemory } from '../../../contexts/MemoryContext'
import { useErrorDisplay } from '../../../hooks/useErrorDisplay'
import { BaseToggle } from '../base/BaseToggle'
import UnifiedErrorDisplay from '../../UnifiedErrorDisplay'
import type { MemoryToggleProps } from '../types'

export const MemoryToggle: React.FC<MemoryToggleProps> = ({
  onMemoryChange,
  className = '',
  disabled = false
}) => {
  const { memoryEnabled, setMemoryEnabled } = useMemory()
  const { error, showTemporaryError, clearError } = useErrorDisplay()

  const handleToggle = useCallback(async (checked: boolean) => {
    try {
      setMemoryEnabled(checked)
      onMemoryChange?.(checked)
      
      // Show feedback to user
      const message = checked 
        ? 'Memory enabled - AI will remember context' 
        : 'Memory disabled - AI will not use previous context'
      console.log(message)
    } catch (error) {
      console.error('Failed to toggle memory status:', error)
      showTemporaryError('Failed to toggle memory. Please try again.', 3000)
    }
  }, [setMemoryEnabled, onMemoryChange, showTemporaryError])

  return (
    <>
      <BaseToggle
        checked={memoryEnabled}
        onChange={handleToggle}
        disabled={disabled}
        className={className}
        ariaLabel={memoryEnabled ? "Disable memory injection" : "Enable memory injection"}
        data-testid="memory-toggle"
      />
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  )
}