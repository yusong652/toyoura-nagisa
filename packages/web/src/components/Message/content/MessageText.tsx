import React from 'react'
import ReactMarkdown from 'react-markdown'
import { MessageTextProps } from '../types'

/**
 * Simple message text display component.
 * 
 * Renders message text content using ReactMarkdown for formatting support.
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
      <ReactMarkdown>{content}</ReactMarkdown>
    </div>
  )
}

export default MessageText