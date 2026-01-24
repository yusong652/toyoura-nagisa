import React from 'react'
import MarkdownContent from '../content/MarkdownContent'
import { StreamingTextRendererProps } from '../types'
import { cleanTextForDisplay } from '@toyoura-nagisa/core/utils'

/**
 * Streaming text renderer component.
 *
 * Handles streaming text display with chunk-based animations for bot messages.
 * Focuses purely on text content rendering without tool state coupling.
 * Filters out emotion keyword markers ([[keyword]]) before rendering.
 *
 * Args:
 *     displayText: Current accumulated text content
 *     chunks: Array of text chunks for animation
 *     streaming: Whether message is currently streaming
 *     isLoading: Whether message is in loading state
 *     className: Optional CSS class name
 *
 * Returns:
 *     JSX element with streaming text or null if no content
 */
const StreamingTextRenderer: React.FC<StreamingTextRendererProps> = ({
  displayText,
  streaming,
  isLoading,
  className = 'message-text'
}) => {
  // Clean text content - remove emotion keywords before display
  const textToDisplay = cleanTextForDisplay(displayText)

  // Use non-streaming rendering when not streaming
  const shouldUseNonStreaming = !streaming

  if (shouldUseNonStreaming) {
    if (textToDisplay) {
      return (
        <div className={className}>
          <MarkdownContent content={textToDisplay} />
        </div>
      )
    } else {
      return null
    }
  }

  // Show minimal placeholder for empty streaming text (e.g., tool calls without text)
  if (!textToDisplay && (streaming || isLoading)) {
    return (
      <div className={`${className} streaming-placeholder`} style={{ minHeight: '1px' }} />
    )
  }
  
  // For streaming, we render the current accumulated text using MarkdownContent
  // Note: Modern Markdown libraries handle partial content well enough for streaming
  return (
    <div className={`${className} streaming-text`}>
      <MarkdownContent content={textToDisplay} />
      {streaming && <span className="streaming-cursor">▌</span>}
    </div>
  )
}

export default StreamingTextRenderer
