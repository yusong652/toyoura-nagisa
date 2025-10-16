import React from 'react'
import MessageText from '../content/MessageText'
import MessageFiles from '../content/MessageFiles'
import MessageTimestamp from '../content/MessageTimestamp'
import { UserMessageRendererProps } from '../types'

/**
 * User message renderer component.
 * 
 * Renders user messages with simple, clean layout including text content,
 * file attachments, and timestamp. No complex streaming or tool logic needed.
 * 
 * Args:
 *     message: Message object with user content
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
  const { text, files, isLoading } = message
  
  return (
    <div className="message-content">
      <MessageText content={text || ''} />
      
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