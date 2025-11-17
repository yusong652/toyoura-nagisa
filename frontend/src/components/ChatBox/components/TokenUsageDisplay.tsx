/**
 * TokenUsageDisplay Component
 *
 * Displays token usage statistics from the most recent LLM response,
 * showing remaining context window capacity.
 */

import React, { useMemo, useRef, useEffect } from 'react'
import { Message, TokenUsage } from '../../../types/chat'
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
  // Store the last known usage to persist across updates
  const lastKnownUsageRef = useRef<TokenUsage | null>(null)

  // Get the most recent assistant message with usage information
  const latestUsage = useMemo(() => {
    // Find the last COMPLETED (non-streaming) assistant message that has usage data
    // Ignore streaming messages to avoid showing default values during streaming
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i]
      const hasContent = msg.content && msg.content.length > 0

      // CRITICAL: Only use completed messages that:
      // 1. Are assistant messages
      // 2. Are NOT streaming
      // 3. Have usage data
      // 4. Have actual content (not empty placeholders)
      if (msg.role === 'assistant' && !msg.streaming && msg.usage && hasContent) {
        return msg.usage
      }
    }

    return null
  }, [messages])

  // Update lastKnownUsageRef when we find new usage data
  useEffect(() => {
    if (latestUsage) {
      lastKnownUsageRef.current = latestUsage
    }
  }, [latestUsage])

  // Use latest usage if available, otherwise keep last known value
  // NEVER fallback to default values - this prevents the "100%" jump issue
  const displayUsage = latestUsage || lastKnownUsageRef.current

  // Only use defaults on first render when we have no data at all
  const tokens_left = displayUsage?.tokens_left ?? 128000  // Default 128k tokens only on first render
  const prompt_tokens = displayUsage?.prompt_tokens ?? 0
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
