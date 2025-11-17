/**
 * TokenUsageDisplay Component
 *
 * Displays token usage statistics from the most recent LLM response,
 * showing remaining context window capacity.
 */

import React, { useMemo } from 'react'
import { Message } from '../../../types/chat'
import './TokenUsageDisplay.css'

interface TokenUsageDisplayProps {
  messages: Message[]
}

/**
 * Format number with thousands separators for better readability
 */
const formatNumber = (num: number): string => {
  return num.toLocaleString('en-US')
}

const TokenUsageDisplay: React.FC<TokenUsageDisplayProps> = ({ messages }) => {
  // Get the most recent assistant message with usage information
  const latestUsage = useMemo(() => {
    // Find the last assistant message that has usage data
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      if (msg.role === 'assistant' && msg.usage) {
        return msg.usage
      }
    }
    return null
  }, [messages])

  // Default values when no usage data available
  const tokens_left = latestUsage?.tokens_left ?? 1048576  // 1M tokens for Gemini 2.0 Flash
  const prompt_tokens = latestUsage?.prompt_tokens ?? 0

  // Calculate percentage of context window used
  const contextUsedPercent = prompt_tokens > 0
    ? Math.min(100, Math.round((prompt_tokens / (prompt_tokens + tokens_left)) * 100))
    : 0

  return (
    <div className="token-usage-display">
      <div className="token-info">
        <span className="token-label">Context</span>
        <span className="token-value">{formatNumber(tokens_left)}</span>
      </div>
      <div className="context-bar">
        <div
          className="context-used"
          style={{ width: `${contextUsedPercent}%` }}
        />
      </div>
    </div>
  )
}

export default TokenUsageDisplay
