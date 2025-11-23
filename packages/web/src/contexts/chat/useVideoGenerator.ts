import { useCallback } from 'react'
import { v4 as uuidv4 } from 'uuid'
import { Message } from '@aiNagisa/core'
import { chatService, sessionService } from '../../services/api'

interface UseVideoGeneratorProps {
  currentSessionId: string | null
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

interface VideoGeneratorResult {
  success: boolean
  video_path?: string
  error?: string
}

/**
 * Hook for video generation from images.
 * 
 * This hook provides video generation functionality that:
 * - Generates videos from the most recent image in a session
 * - Supports different motion styles for video generation
 * - Automatically adds generated videos to the message list
 * - Handles error states gracefully
 * 
 * The hook integrates with the backend video generation API which uses
 * ComfyUI for image-to-video conversion with motion effects.
 * 
 * Args:
 *     currentSessionId: Current active session ID
 *     setMessages: State setter for updating message list
 * 
 * Returns:
 *     Object containing generateVideo function
 * 
 * TypeScript Learning Points:
 * - Custom hook with dependency injection pattern
 * - Async function handling within hooks
 * - Type-safe API integration
 * - Error boundary pattern for API calls
 */
export const useVideoGenerator = ({
  currentSessionId,
  setMessages
}: UseVideoGeneratorProps) => {

  const generateVideo = useCallback(async (
    sessionId: string,
    motionStyle?: string
  ): Promise<VideoGeneratorResult> => {

    try {
      const result = await chatService.generateVideo(sessionId, motionStyle)
      
      if (result.success && sessionId === currentSessionId) {
        try {
          const historyData = await sessionService.getSessionHistory(sessionId)
          
          if (historyData.history && Array.isArray(historyData.history)) {
            const lastVideoMessage = historyData.history
              .filter((msg: any) => msg.role === 'video')
              .pop()

            if (lastVideoMessage && lastVideoMessage.video_path) {
              // Extract filename and determine media type
              const videoPath = lastVideoMessage.video_path
              const filename = videoPath?.split('/').pop() || 'video.mp4'
              const extension = filename.toLowerCase().split('.').pop()
              let mediaType = 'video/mp4' // default
              
              if (extension === 'gif') {
                mediaType = 'image/gif'
              } else if (extension === 'webm') {
                mediaType = 'video/webm'
              } else if (extension === 'mp4') {
                mediaType = 'video/mp4'
              }

              const videoMessage: Message = {
                id: lastVideoMessage.id || uuidv4(),
                role: 'assistant',  // ✨ Use role instead of sender: 'bot'
                text: lastVideoMessage.content || '',
                timestamp: new Date(lastVideoMessage.timestamp || Date.now()).getTime(),
                files: [{
                  name: filename,
                  type: mediaType,
                  data: `/api/videos/${lastVideoMessage.video_path}`
                }]
              }

              setMessages(prev => [...prev, videoMessage])
            }
          }
        } catch (error) {
          console.error('Failed to retrieve generated video message:', error)
        }
      }
      
      return result
    } catch (error) {
      console.error('Video generation failed:', error)
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Video generation failed'
      }
    }
  }, [currentSessionId, setMessages])

  return {
    generateVideo
  }
}