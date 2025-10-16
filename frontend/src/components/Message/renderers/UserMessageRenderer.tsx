import React from 'react'
import MessageText from '../content/MessageText'
import MessageFiles from '../content/MessageFiles'
import MessageTimestamp from '../content/MessageTimestamp'
import ToolResultBlock from '../content/ToolResultBlock'
import { UserMessageRendererProps } from '../types'

/**
 * User message renderer component.
 *
 * Renders user messages with simple, clean layout including text content,
 * file attachments, and timestamp. Also handles tool_result messages that
 * display tool execution results.
 *
 * Args:
 *     message: Message object with user content or tool results
 *     isSelected: Whether message is currently selected
 *     onMessageClick: Message click handler for selection
 *     onImageClick: Image click handler for viewer
 *
 * Returns:
 *     JSX element with rendered user message content
 */
const UserMessageRenderer: React.FC<UserMessageRendererProps> = ({
  message,
  onImageClick
}) => {
  const { text, files, isLoading, content } = message

  // Render content blocks if available (for tool_result messages)
  const renderContentBlocks = () => {
    if (!content || content.length === 0) {
      // Regular user text message
      return <MessageText content={text || ''} />
    }

    // Render structured content blocks (tool_result)
    return content.map((block, index) => {
      switch (block.type) {
        case 'text':
          return <MessageText key={index} content={block.text || ''} />
        case 'tool_result':
          return <ToolResultBlock key={index} block={block} />
        default:
          return null
      }
    })
  }

  return (
    <div className="message-content">
      {/* Render content blocks or legacy text */}
      {renderContentBlocks()}

      {/* Render file attachments */}
      {files && files.length > 0 && !isLoading && (
        <MessageFiles
          files={files}
          isLoading={isLoading}
          onImageClick={onImageClick}
          role="user"
        />
      )}

      <MessageTimestamp timestamp={message.timestamp} />
    </div>
  )
}

export default UserMessageRenderer