import React from 'react'
import ReactMarkdown from 'react-markdown'
import { StreamingTextRendererProps } from '../types'
import { cleanTextForDisplay } from '@aiNagisa/core/utils'

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
  chunks,
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
          <ReactMarkdown>{textToDisplay}</ReactMarkdown>
        </div>
      )
    } else {
      return null
    }
  }

  // Show minimal placeholder for empty streaming text (e.g., tool calls without text)
  // This ensures message container is rendered, but without visible content
  if (!textToDisplay && (streaming || isLoading)) {
    return (
      <div className={`${className} streaming-placeholder`} style={{ minHeight: '1px' }} />
    )
  }
  
  // Streaming animation rendering
  const renderedText = textToDisplay
  const lastChunkStart = renderedText.length - (chunks[chunks.length - 1]?.length || 0)
  
  return renderedText ? (
    <div className={`${className} streaming-text`}>
      {/* Render completed portion */}
      {lastChunkStart > 0 && (
        <div className="completed-text">
          <ReactMarkdown>{renderedText.slice(0, lastChunkStart)}</ReactMarkdown>
        </div>
      )}
      {/* Render latest chunk with animation */}
      {chunks.length > 0 && (
        <div key={`chunk-${chunks.length}`} className="fade-in-chunk">
          <ReactMarkdown>{renderedText.slice(lastChunkStart)}</ReactMarkdown>
        </div>
      )}
    </div>
  ) : null
}

export default StreamingTextRenderer