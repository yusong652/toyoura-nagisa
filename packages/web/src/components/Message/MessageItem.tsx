import React, { useState } from 'react'
import './MessageItem.css'
import { Message } from '@aiNagisa/core'
import { useImageNavigation } from '../../hooks/useImageNavigation'
import { useErrorDisplay } from '../../hooks/useErrorDisplay'
import ImageViewer from '../ImageViewer'
import VideoPlayer from '../VideoPlayer'
import { VideoFormat } from '../VideoPlayer/types'
import UnifiedErrorDisplay from '../UnifiedErrorDisplay'

// New architecture components
import { useMessageState, useMessageEvents } from './hooks'
import UserMessageRenderer from './renderers/UserMessageRenderer'
import BotMessageRenderer from './renderers/BotMessageRenderer'
import MessageAvatar from './avatar/MessageAvatar'
import { showAvatarTooltip, hideAvatarTooltip } from './avatar/AvatarTooltip'
import MessageActions from './actions/MessageActions'
import MessageStatusComponent from './content/MessageStatus'

interface MessageItemProps {
  message: Message
  onMessageSelect: (id: string | null) => void
  selectedMessageId: string | null
  allMessages: Message[]
}

/**
 * Refactored MessageItem component with clean architecture.
 * 
 * Main container component that orchestrates message display using specialized
 * renderer components and centralized state management. Separates user and bot
 * message logic for better maintainability.
 * 
 * Args:
 *     message: Message object with content and metadata
 *     onMessageSelect: Function to handle message selection
 *     selectedMessageId: Currently selected message ID
 *     allMessages: All messages for image navigation
 * 
 * Returns:
 *     JSX element with complete message display including modals
 */
const MessageItem: React.FC<MessageItemProps> = ({
  message,
  onMessageSelect,
  selectedMessageId,
  allMessages
}) => {
  const { role, content } = message

  // Check if this message contains tool-related content blocks
  const hasToolContent = content?.some(block =>
    block.type === 'tool_use' ||
    block.type === 'tool_result' ||
    block.type === 'thinking'
  )

  // Check if this is a tool_result message (user role with tool_result content)
  const isToolResultMessage = role === 'user' &&
    content?.some(block => block.type === 'tool_result')
  
  // Modal states
  const [viewerOpen, setViewerOpen] = useState(false)
  const [currentImageUrl, setCurrentImageUrl] = useState<string>('')
  const [showVideoPlayer, setShowVideoPlayer] = useState(false)
  const [currentVideoUrl, setCurrentVideoUrl] = useState<string>('')
  const [currentVideoFormat, setCurrentVideoFormat] = useState<VideoFormat>('mp4')
  
  // Hooks for state and events
  const { isSelected } = useMessageState(message, selectedMessageId)
  const { error, clearError } = useErrorDisplay()
  const { allImages, getImageIndex } = useImageNavigation(allMessages)
  
  const eventHandlers = useMessageEvents(
    message,
    isSelected,
    onMessageSelect,
    setCurrentImageUrl,
    setViewerOpen,
    setCurrentVideoUrl,
    setCurrentVideoFormat,
    setShowVideoPlayer
  )
  
  // Avatar event handlers
  const handleAvatarMouseEnter = (e: React.MouseEvent<HTMLImageElement>) => {
    showAvatarTooltip(e, role)
  }
  
  const handleAvatarMouseLeave = () => {
    hideAvatarTooltip()
  }
  
  // Determine effective role for display (CSS class name)
  let displayRole: string = role
  if (isToolResultMessage) {
    displayRole = 'tool-result'
  } else if (hasToolContent) {
    displayRole = 'tool-message'
  }

  return (
    <>
      <div
        className={`message ${displayRole} ${isSelected ? 'selected' : ''}`}
        onClick={eventHandlers.onMessageClick}
      >
        {/* Hide avatar for tool_result messages */}
        {!isToolResultMessage && (
          <MessageAvatar
            role={role}
            onMouseEnter={handleAvatarMouseEnter}
            onMouseLeave={handleAvatarMouseLeave}
          />
        )}

        {role === 'assistant' ? (
          <BotMessageRenderer
            message={message}
            isSelected={isSelected}
            onMessageClick={eventHandlers.onMessageClick}
            onImageClick={eventHandlers.onImageClick}
            onVideoClick={eventHandlers.onVideoClick}
          />
        ) : (
          <UserMessageRenderer
            message={message}
            isSelected={isSelected}
            onMessageClick={eventHandlers.onMessageClick}
            onImageClick={eventHandlers.onImageClick}
          />
        )}
        
        <MessageStatusComponent
          status={message.status}
          role={role}
        />
        
        <MessageActions
          messageId={message.id}
          isSelected={isSelected}
          isLoading={message.isLoading}
          streaming={message.streaming}
          onDelete={eventHandlers.onDeleteMessage}
        />
      </div>
      
      {/* Image Viewer Modal */}
      {viewerOpen && currentImageUrl && allImages.length > 0 && (
        <ImageViewer
          open={viewerOpen}
          onClose={() => setViewerOpen(false)}
          images={allImages.map(img => img.url)}
          initialIndex={getImageIndex(currentImageUrl)}
          imageNames={allImages.map(img => img.name)}
        />
      )}
      
      {/* Video Player Modal */}
      {showVideoPlayer && currentVideoUrl && (
        <VideoPlayer
          videoUrl={currentVideoUrl}
          format={currentVideoFormat}
          onClose={() => setShowVideoPlayer(false)}
          autoPlay={true}
          loop={true}
        />
      )}
      
      {/* Error Display */}
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  )
}

export default MessageItem