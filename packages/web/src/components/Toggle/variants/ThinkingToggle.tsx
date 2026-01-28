/**
 * Thinking Toggle Component
 *
 * Toggle for enabling/disabling extended thinking/reasoning mode in LLM responses.
 * When enabled, LLM providers will use their extended reasoning capabilities:
 * - Google Gemini: thinking_config with thinking_level "high"
 * - OpenAI: reasoning with effort "medium"
 * - Anthropic Claude: extended thinking with budget_tokens
 * - Moonshot K2.5: thinking type "enabled"
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
  const { thinkingEnabled, setThinkingEnabled, isToggling } = useThinking()
  const { error, showTemporaryError, clearError } = useErrorDisplay()

  const handleToggle = useCallback(async (checked: boolean) => {
    try {
      await setThinkingEnabled(checked)
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
  }, [setThinkingEnabled, onThinkingChange, showTemporaryError])

  return (
    <>
      <BaseToggle
        checked={thinkingEnabled}
        onChange={handleToggle}
        disabled={disabled || isToggling}
        className={className}
        ariaLabel={thinkingEnabled ? "Disable thinking mode" : "Enable thinking mode"}
        data-testid="thinking-toggle"
      />
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  )
}
