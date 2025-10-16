import React, { useState } from 'react'
import { ToolUseBlock as ToolUseBlockType } from '../../../types/chat'

interface ToolUseBlockProps {
  block: ToolUseBlockType
}

/**
 * Tool use block component for displaying tool calls.
 *
 * Shows the tool name, input parameters in a collapsible format.
 * Supports multiple tool calls in a single message.
 *
 * Args:
 *     block: ToolUseBlock object with tool name and input parameters
 *
 * Returns:
 *     JSX element with tool call display
 */
const ToolUseBlock: React.FC<ToolUseBlockProps> = ({ block }) => {
  const [isExpanded, setIsExpanded] = useState(false)

  const hasInput = block.input && Object.keys(block.input).length > 0

  return (
    <div className="tool-use-block">
      <div className="tool-use-header">
        <span className="tool-use-prompt">$</span>
        <span className="tool-use-name">{block.name}</span>
        {hasInput && (
          <button
            className="tool-use-toggle"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse parameters' : 'Expand parameters'}
          >
            {isExpanded ? '−' : '+'}
          </button>
        )}
      </div>

      {hasInput && isExpanded && (
        <div className="tool-use-input">
          <pre className="tool-use-input-content">
            {JSON.stringify(block.input, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}

export default ToolUseBlock
