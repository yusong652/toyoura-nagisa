import React from 'react'
import ReactMarkdown from 'react-markdown'
import { StreamingTextRendererProps } from '../types'

/**
 * Streaming text renderer component.
 * 
 * Handles complex streaming text display with chunk-based animations and
 * tool action text integration for bot messages.
 * 
 * Args:
 *     displayText: Current accumulated text
 *     chunks: Array of text chunks for animation
 *     streaming: Whether message is currently streaming
 *     isLoading: Whether message is in loading state
 *     toolState: Optional tool state for action text
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
  toolState,
  className = 'message-text'
}) => {
  // Determine what text to display (action text or display text)
  const textToDisplay = (toolState?.isUsingTool && toolState?.action) 
    ? toolState.action 
    : displayText
    
  // Use non-streaming rendering for tool action text or when not streaming
  const shouldUseNonStreaming = !streaming || (toolState?.isUsingTool && toolState?.action)
  
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