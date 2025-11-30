import React, { useState } from 'react'
import { ToolResultBlock as ToolResultBlockType } from '@toyoura-nagisa/core'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

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

  // Extract text content from parts
  const textContent = block.content.parts
    .filter(part => part.type === 'text')
    .map(part => part.text)
    .join('\n')

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
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  code({ node, inline, className, children, ...props }: any) {
                    return inline ? (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    ) : (
                      <pre className="code-block">
                        <code className={className} {...props}>
                          {children}
                        </code>
                      </pre>
                    )
                  }
                }}
              >
                {textContent}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ToolResultBlock
