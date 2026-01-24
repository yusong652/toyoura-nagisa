import React from 'react'
import MarkdownContent from './MarkdownContent'
import { MessageTextProps } from '../types'

/**
 * Simple message text display component.
 * 
 * Renders message text content using MarkdownContent for high-quality formatting support.
 * Used for both user and bot messages when simple text rendering is needed.
 * 
 * Args:
 *     content: Text content to render
 *     className: Optional CSS class name for styling
 * 
 * Returns:
 *     JSX element with formatted text content or null if no content
 */
const MessageText: React.FC<MessageTextProps> = ({ content, className = 'message-text' }) => {
  if (!content) return null
  
  return (
    <div className={className}>
      <MarkdownContent content={content} />
    </div>
  )
}

export default MessageText
