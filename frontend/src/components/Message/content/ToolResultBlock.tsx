import React, { useState } from 'react'
import { ToolResultBlock as ToolResultBlockType } from '../../../types/chat'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface ToolResultBlockProps {
  block: ToolResultBlockType
}

/**
 * Tool result block component for displaying tool execution results.
 *
 * Shows tool results with proper formatting, supports both success and error states.
 * Handles text content with markdown rendering and collapsible display for long results.
 *
 * Args:
 *     block: ToolResultBlock object with tool name, content, and error status
 *
 * Returns:
 *     JSX element with tool result display
 */
const ToolResultBlock: React.FC<ToolResultBlockProps> = ({ block }) => {
  const [isExpanded, setIsExpanded] = useState(true)

  // Extract text content from parts
  const textContent = block.content.parts
    .filter(part => part.type === 'text')
    .map(part => part.text)
    .join('\n')

  const isLongContent = textContent.length > 500
  const displayContent = isExpanded || !isLongContent
    ? textContent
    : textContent.substring(0, 500) + '...'

  return (
    <div className={`tool-result-block ${block.is_error ? 'error' : 'success'}`}>
      <div className="tool-result-header">
        <div className="tool-result-icon">
          {block.is_error ? '❌' : '✅'}
        </div>
        <div className="tool-result-info">
          <div className="tool-result-name">{block.tool_name}</div>
          <div className="tool-result-status">
            {block.is_error ? 'Error' : 'Success'}
          </div>
        </div>
        {isLongContent && (
          <button
            className="tool-result-toggle"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Collapse result' : 'Expand result'}
          >
            {isExpanded ? '▼' : '▶'}
          </button>
        )}
      </div>

      <div className="tool-result-content">
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
          {displayContent}
        </ReactMarkdown>
      </div>
    </div>
  )
}

export default ToolResultBlock
