import React, { useState } from 'react'
import { ThinkingBlock as ThinkingBlockType } from '@toyoura-nagisa/core'
import ReactMarkdown from 'react-markdown'

interface ThinkingBlockProps {
  block: ThinkingBlockType
  streaming?: boolean  // Whether the thinking content is still streaming
}

/**
 * Thinking block component for displaying AI reasoning process.
 *
 * Shows the AI's internal thought process with scrollable viewport.
 * Default expanded with limited height for better UX.
 * Displays streaming indicator (blinking cursor) when content is still streaming.
 * Useful for debugging and understanding AI decision-making.
 *
 * Args:
 *     block: ThinkingBlock object with thinking content
 *     streaming: Optional flag indicating if content is still streaming
 *
 * Returns:
 *     JSX element with thinking content display
 */
const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ block, streaming = false }) => {
  // Default to expanded state for better visibility (as per user preference)
  const [isExpanded, setIsExpanded] = useState(true)

  return (
    <div className="thinking-block">
      <div
        className="thinking-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="thinking-prompt">#</span>
        <span className="thinking-title">thinking</span>
        {streaming && (
          <span className="thinking-streaming-badge" title="Streaming in progress">
            ●
          </span>
        )}
        <button
          className="thinking-toggle"
          aria-label={isExpanded ? 'Collapse thinking' : 'Expand thinking'}
        >
          {isExpanded ? '−' : '+'}
        </button>
      </div>

      {isExpanded && (
        <div className="thinking-content">
          <div className="thinking-viewport">
            <div className="thinking-scrollable">
              <ReactMarkdown>{block.thinking}</ReactMarkdown>
              {streaming && <span className="streaming-cursor">▌</span>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ThinkingBlock
