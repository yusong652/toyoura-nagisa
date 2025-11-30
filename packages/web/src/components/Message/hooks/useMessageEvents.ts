import { useCallback } from 'react'
import { Message } from '@toyoura-nagisa/core'
import { useChat } from '../../../contexts/chat/ChatContext'
import { useErrorDisplay } from '../../../hooks/useErrorDisplay'
import { VideoFormat } from '../../VideoPlayer/types'
import { MessageEventHandlers } from '../types'

/**
 * Hook for managing message event handlers.
 * 
 * Provides standardized event handlers for message interactions including
 * selection, deletion, and file interactions.
 * 
 * Args:
 *     message: Message object containing id and other properties
 *     isSelected: Current selection state
 *     onMessageSelect: Function to handle message selection
 *     setCurrentImageUrl: Function to set current image URL for viewer
 *     setViewerOpen: Function to control image viewer visibility
 *     setCurrentVideoUrl: Function to set current video URL for player
 *     setCurrentVideoFormat: Function to set video format (VideoFormat type)
 *     setShowVideoPlayer: Function to control video player visibility
 *
 * Returns:
 *     MessageEventHandlers: Object containing standardized event handlers:
 *         - onMessageClick: (e: React.MouseEvent) => void
 *         - onDeleteMessage: (e: React.MouseEvent) => void
 *         - onImageClick: (imageUrl: string) => void
 *         - onVideoClick: (videoUrl: string, format?: VideoFormat) => void
 */
export const useMessageEvents = (
  message: Message,
  isSelected: boolean,
  onMessageSelect: (id: string | null) => void,
  setCurrentImageUrl: React.Dispatch<React.SetStateAction<string>>,
  setViewerOpen: React.Dispatch<React.SetStateAction<boolean>>,
  setCurrentVideoUrl: React.Dispatch<React.SetStateAction<string>>,
  setCurrentVideoFormat: React.Dispatch<React.SetStateAction<VideoFormat>>,
  setShowVideoPlayer: React.Dispatch<React.SetStateAction<boolean>>
): MessageEventHandlers => {
  const { deleteMessage } = useChat()
  const { showTemporaryError } = useErrorDisplay()
  
  const handleMessageClick = useCallback((e: React.MouseEvent) => {
    // Don't trigger selection if clicking on file
    if ((e.target as HTMLElement).closest('.file-image')) {
      return
    }
    onMessageSelect(isSelected ? null : message.id)
  }, [isSelected, message.id, onMessageSelect])
  
  const handleDeleteMessage = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!message.id) return
    
    try {
      await deleteMessage(message.id)
      // Clear selection after deletion
      onMessageSelect(null)
    } catch (error) {
      console.error('删除消息失败:', error)
      showTemporaryError('Failed to delete message. Please try again.', 4000)
    }
  }, [message.id, deleteMessage, onMessageSelect, showTemporaryError])
  
  const handleImageClick = useCallback((imageUrl: string) => {
    setCurrentImageUrl(imageUrl)
    setViewerOpen(true)
  }, [setCurrentImageUrl, setViewerOpen])
  
  const handleVideoClick = useCallback((videoUrl: string, format: VideoFormat = 'mp4') => {
    setCurrentVideoUrl(videoUrl)
    setCurrentVideoFormat(format)
    setShowVideoPlayer(true)
  }, [setCurrentVideoUrl, setCurrentVideoFormat, setShowVideoPlayer])
  
  return {
    onMessageClick: handleMessageClick,
    onDeleteMessage: handleDeleteMessage,
    onImageClick: handleImageClick,
    onVideoClick: handleVideoClick
  }
}