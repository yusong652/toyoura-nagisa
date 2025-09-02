import React from 'react'
import FilePreview from '../files/FilePreview'
import { MessageFilesProps } from '../types'

/**
 * Message files container component.
 * 
 * Manages the display of file attachments in messages including images,
 * videos, and documents with appropriate preview components.
 * 
 * Args:
 *     files: Array of file objects to display
 *     isLoading: Whether message is currently loading
 *     onImageClick: Image click handler for viewer
 *     onVideoClick: Optional video click handler for player
 *     sender: Message sender type for context
 * 
 * Returns:
 *     JSX element with file previews or null if no files/loading
 */
const MessageFiles: React.FC<MessageFilesProps> = ({
  files,
  isLoading,
  onImageClick,
  onVideoClick,
  sender
}) => {
  if (!files || files.length === 0 || isLoading) return null
  
  return (
    <div className="message-files">
      {files.map((file, index) => (
        <FilePreview
          key={index}
          file={file}
          onImageClick={onImageClick}
          onVideoClick={onVideoClick}
          sender={sender}
        />
      ))}
    </div>
  )
}

export default MessageFiles