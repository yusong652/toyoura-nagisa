import React from 'react'
import StreamingTextRenderer from './StreamingTextRenderer'
import MessageFiles from '../content/MessageFiles'
import MessageTimestamp from '../content/MessageTimestamp'
import { ToolStateDisplay } from '../../Tools'
import { BotMessageRendererProps } from '../types'

/**
 * Bot message renderer component.
 * 
 * Renders complex bot messages with tool state display, streaming text,
 * file attachments, and timestamp. Handles both streaming and static content.
 * 
 * Args:
 *     message: Message object with bot content and tool state
 *     isSelected: Whether message is currently selected
 *     onMessageClick: Message click handler for selection
 *     onImageClick: Image click handler for viewer
 *     onVideoClick: Video click handler for player
 * 
 * Returns:
 *     JSX element with rendered bot message content
 */
const BotMessageRenderer: React.FC<BotMessageRendererProps> = ({
  message,
  onImageClick,
  onVideoClick
}) => {
  const { toolState, files, isLoading, streaming, text } = message
  
  // We need to use the streaming text hook for proper text handling
  const displayText = text || ''
  const chunks: string[] = [] // Simplified for now - full streaming logic in hook if needed
  
  const hasContent = displayText || (toolState?.isUsingTool && toolState?.action)
  const hasFiles = files && files.length > 0 && !isLoading
  const shouldShowContent = hasContent || hasFiles
  
  return (
    <div className="message-wrapper">
      {/* Show stored tool state for historical messages (WebSocket tool state shown in ChatBox) */}
      {toolState && <ToolStateDisplay toolState={toolState} />}
      
      {shouldShowContent && (
        <div className="message-content">
          {hasContent && (
            <StreamingTextRenderer
              displayText={displayText || ''}
              chunks={chunks || []}
              streaming={streaming || false}
              isLoading={isLoading || false}
              toolState={toolState}
            />
          )}
          
          {hasFiles && (
            <MessageFiles 
              files={files}
              isLoading={isLoading || false}
              onImageClick={onImageClick}
              onVideoClick={onVideoClick}
              sender="bot"
            />
          )}
          
          <MessageTimestamp timestamp={message.timestamp} />
        </div>
      )}
    </div>
  )
}

export default BotMessageRenderer