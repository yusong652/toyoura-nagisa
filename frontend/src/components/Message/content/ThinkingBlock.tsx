import React, { useState } from 'react'
import { ThinkingBlock as ThinkingBlockType } from '../../../types/chat'
import ReactMarkdown from 'react-markdown'

interface ThinkingBlockProps {
  block: ThinkingBlockType
}

/**
 * Thinking block component for displaying AI reasoning process.
 *
 * Shows the AI's internal thought process with scrollable viewport.
 * Default expanded with limited height for better UX.
 * Useful for debugging and understanding AI decision-making.
 *
 * Args:
 *     block: ThinkingBlock object with thinking content
 *
 * Returns:
 *     JSX element with thinking content display
 */
const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ block }) => {
  // Default to expanded state for better visibility
  const [isExpanded, setIsExpanded] = useState(true)

  return (
    <div className="thinking-block">
      <div
        className="thinking-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <span className="thinking-prompt">#</span>
        <span className="thinking-title">thinking</span>
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
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ThinkingBlock
