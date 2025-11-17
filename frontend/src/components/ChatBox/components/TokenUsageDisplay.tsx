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
 * Format tokens in K units (e.g., 128000 -> "128k")
 */
const formatTokensK = (tokens: number): string => {
  const k = Math.round(tokens / 1000)
  return `${k}k`
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
  const tokens_left = latestUsage?.tokens_left ?? 128000  // Default 128k tokens
  const prompt_tokens = latestUsage?.prompt_tokens ?? 0
  const total_capacity = prompt_tokens + tokens_left

  // Calculate percentage remaining
  const remainingPercent = total_capacity > 0
    ? Math.round((tokens_left / total_capacity) * 100)
    : 100

  return (
    <div className="token-usage-display">
      <div className="token-info">
        <span className="token-label">Context</span>
        <span className="token-value">{remainingPercent}% ({formatTokensK(tokens_left)})</span>
      </div>
      <div className="context-bar">
        <div
          className="context-used"
          style={{ width: `${100 - remainingPercent}%` }}
        />
      </div>
    </div>
  )
}

export default TokenUsageDisplay
