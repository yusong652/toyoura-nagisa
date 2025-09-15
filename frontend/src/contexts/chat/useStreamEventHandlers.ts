import { useCallback } from 'react'
import { playMotion } from '../../utils/live2d'

interface UseStreamEventHandlersProps {
  currentSessionId: string | null
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  updateMessageId: (oldId: string, newId: string) => void
  addImageMessage: (imageData: any) => void
  processChunk: (chunk: any, messageId: string) => Promise<void>
  updateTTSMessageId?: (oldId: string, newId: string) => void
}

interface StreamEventHandlers {
  handleTitleUpdate: (data: any) => void
  handleSessionRefresh: (data: any) => Promise<void>
  handleAiMessageId: (data: any, botMessageId: string) => string | null
  handleKeyword: (data: any) => void
  handleContentUpdate: (data: any, messageId: string) => Promise<void>
}

/**
 * Hook for handling various stream events.
 * 
 * Centralizes event handling logic for stream processing.
 * Extracted from useStreamHandler for better organization.
 */
export const useStreamEventHandlers = ({
  currentSessionId,
  sessionRefreshSessions,
  sessionSwitchSession,
  updateMessageId,
  addImageMessage,
  processChunk,
  updateTTSMessageId
}: UseStreamEventHandlersProps): StreamEventHandlers => {
  
  /**
   * Handle title update event.
   * 
   * Refreshes session list when title is updated.
   */
  const handleTitleUpdate = useCallback((data: any) => {
    if (data.payload && data.payload.session_id && data.payload.title) {
      sessionRefreshSessions().catch(error => {
        console.error('[EventHandlers] Failed to refresh sessions:', error)
      })
    }
  }, [sessionRefreshSessions])

  /**
   * Handle session refresh event.
   * 
   * Refreshes current session content when requested by server.
   */
  const handleSessionRefresh = useCallback(async (data: any) => {
    if (data.payload && data.payload.session_id) {
      const { session_id: refreshSessionId } = data.payload
      
      if (refreshSessionId === currentSessionId) {
        try {
          const response = await fetch(`/api/history/${refreshSessionId}`)
          if (!response.ok) {
            throw new Error(`Failed to fetch history: ${response.status}`)
          }
          
          const historyData = await response.json()
          if (!historyData.history || !Array.isArray(historyData.history)) {
            throw new Error('Invalid history data format')
          }

          // Find last image message
          const lastImageMessage = historyData.history
            .filter((msg: any) => msg.role === 'image')
            .pop()

          if (lastImageMessage) {
            addImageMessage(lastImageMessage)
          }
        } catch (error) {
          console.error('[EventHandlers] Failed to refresh session:', error)
          await sessionSwitchSession(refreshSessionId)
        }
      }
    }
  }, [currentSessionId, sessionSwitchSession, addImageMessage])


  /**
   * Handle AI message ID update.
   * 
   * Updates message ID when server provides final ID.
   * Returns the new ID if updated, null otherwise.
   */
  const handleAiMessageId = useCallback((data: any, botMessageId: string): string | null => {
    if (data.message_id) {
      const newAiMessageId = data.message_id
      updateMessageId(botMessageId, newAiMessageId)

      // Also update TTS message ID tracking
      if (updateTTSMessageId) {
        updateTTSMessageId(botMessageId, newAiMessageId)
      }

      return newAiMessageId
    }
    return null
  }, [updateMessageId, updateTTSMessageId])

  /**
   * Handle keyword for Live2D motion.
   * 
   * Triggers Live2D animation based on keyword.
   */
  const handleKeyword = useCallback((data: any) => {
    if (data.keyword) {
      playMotion(data.keyword)
    }
  }, [])

/**
   * Handle content update (text/audio).
   * 
   * Delegates to chunk processor for handling.
   */
  const handleContentUpdate = useCallback(async (data: any, messageId: string) => {
    if (!data) return
    
    
    await processChunk(data, messageId)
  }, [processChunk])

  return {
    handleTitleUpdate,
    handleSessionRefresh,
    handleAiMessageId,
    handleKeyword,
    handleContentUpdate
  }
}