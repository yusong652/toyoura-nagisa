import React, { useState } from 'react'
import { ThinkingBlock as ThinkingBlockType } from '../../../types/chat'
import ReactMarkdown from 'react-markdown'

interface ThinkingBlockProps {
  block: ThinkingBlockType
}

/**
 * Thinking block component for displaying AI reasoning process.
 *
 * Shows the AI's internal thought process in a collapsible format.
 * Useful for debugging and understanding AI decision-making.
 *
 * Args:
 *     block: ThinkingBlock object with thinking content
 *
 * Returns:
 *     JSX element with thinking content display
 */
const ThinkingBlock: React.FC<ThinkingBlockProps> = ({ block }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  return (
    <div className="thinking-block">
      <div
        className="thinking-header"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="thinking-icon">💭</div>
        <div className="thinking-title">Thinking...</div>
        <button
          className="thinking-toggle"
          aria-label={isExpanded ? 'Collapse thinking' : 'Expand thinking'}
        >
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {isExpanded && (
        <div className="thinking-content">
          <ReactMarkdown>{block.thinking}</ReactMarkdown>
        </div>
      )}
    </div>
  )
}

export default ThinkingBlock
