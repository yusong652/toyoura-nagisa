import React, { useState } from 'react'
import { ToolResultBlock as ToolResultBlockType } from '@toyoura-nagisa/core'
import MarkdownContent from './MarkdownContent'

interface ToolResultBlockProps {
  block: ToolResultBlockType
}

/**
 * Tool result block component for displaying tool execution results.
 *
 * Shows tool results with scrollable viewport and height limit.
 * Supports both success and error states with markdown rendering.
 * Default expanded with limited height for better UX.
 *
 * Args:
 *     block: ToolResultBlock object with tool name, content, and error status
 *
 * Returns:
 *     JSX element with tool result display
 */
const ToolResultBlock: React.FC<ToolResultBlockProps> = ({ block }) => {
  // Default to expanded state for better visibility
  const [isExpanded, setIsExpanded] = useState(true)

  // Extract text content from parts (with null safety like CLI)
  const extractTextContent = (): string => {
    const content = block.content
    if (!content) return ''

    // Handle string content directly
    if (typeof content === 'string') {
      return content
    }

    // Handle object with parts array
    if (typeof content === 'object' && 'parts' in content && Array.isArray(content.parts)) {
      return content.parts
        .filter((part: any) => part.type === 'text')
        .map((part: any) => part.text || '')
        .join('\n')
    }

    return ''
  }

  const textContent = extractTextContent()

  return (
    <div className={`tool-result-block ${block.is_error ? 'error' : 'success'}`}>
      <div className="tool-result-header">
        <span className="tool-result-prompt">{block.is_error ? '✗' : '✓'}</span>
        <span className="tool-result-name">{block.tool_name}</span>
        <button
          className="tool-result-toggle"
          onClick={() => setIsExpanded(!isExpanded)}
          aria-label={isExpanded ? 'Collapse result' : 'Expand result'}
        >
          {isExpanded ? '−' : '+'}
        </button>
      </div>

      {isExpanded && (
        <div className="tool-result-content">
          <div className="tool-result-viewport">
            <div className="tool-result-scrollable">
              <MarkdownContent content={textContent} />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ToolResultBlock
