/**
 * Thinking Toggle Component
 *
 * Toggle for enabling/disabling extended thinking/reasoning mode in LLM responses.
 *
 * Thinking modes:
 * - none: Model does not support thinking (show "Default" label)
 * - always_on: Model always uses thinking (show "Default" label, not configurable)
 * - configurable: Thinking can be toggled via API params
 *
 * Provider-specific behavior:
 * - Google Gemini: thinking_config with thinking_level
 * - OpenAI: reasoning with effort
 * - Anthropic Claude: extended thinking with budget_tokens
 * - Moonshot K2.5: thinking type "enabled"/"disabled"
 */

import React, { useCallback } from 'react'
import { useThinking } from '../../../contexts/ThinkingContext'
import { useErrorDisplay } from '../../../hooks/useErrorDisplay'
import { BaseToggle } from '../base/BaseToggle'
import UnifiedErrorDisplay from '../../UnifiedErrorDisplay'
import type { ThinkingToggleProps } from '../types'

export const ThinkingToggle: React.FC<ThinkingToggleProps> = ({
  onThinkingChange,
  className = '',
  disabled = false
}) => {
  const { thinkingEnabled, thinkingMode, isConfigurable, toggleThinking, isToggling } = useThinking()
  const { error, showTemporaryError, clearError } = useErrorDisplay()

  const handleToggle = useCallback(async (checked: boolean) => {
    if (!isConfigurable) return

    try {
      toggleThinking()
      onThinkingChange?.(checked)

      // Show feedback to user
      const message = checked
        ? 'Thinking enabled - LLM will use extended reasoning'
        : 'Thinking disabled - LLM will use standard mode'
      console.log(message)
    } catch (error) {
      console.error('Failed to toggle thinking status:', error)
      showTemporaryError('Failed to toggle thinking mode. Please try again.', 3000)
    }
  }, [toggleThinking, isConfigurable, onThinkingChange, showTemporaryError])

  // For non-configurable modes (always_on or none), just show "Default" label
  if (!isConfigurable) {
    return (
      <span
        className={className}
        style={{
          fontSize: '12px',
          color: 'var(--text-secondary, #888)',
          fontStyle: 'italic'
        }}
        title={thinkingMode === 'always_on'
          ? 'This model always uses extended thinking'
          : 'Thinking not available for this model'}
      >
        Default
      </span>
    )
  }

  // Disable toggle when toggling is in progress
  const isDisabled = disabled || isToggling

  return (
    <>
      <BaseToggle
        checked={thinkingEnabled}
        onChange={handleToggle}
        disabled={isDisabled}
        className={className}
        ariaLabel={thinkingEnabled
          ? "Disable thinking mode"
          : "Enable thinking mode"}
        data-testid="thinking-toggle"
      />
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  )
}
