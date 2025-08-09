import { useCallback } from 'react'
import { MessageStatus } from '../../types/chat'
import { playMotion } from '../../utils/live2d'

interface UseStreamEventHandlersProps {
  currentSessionId: string | null
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  updateMessageStatus: (messageId: string, status: MessageStatus) => void
  updateMessageId: (oldId: string, newId: string) => void
  addImageMessage: (imageData: any) => void
  handleToolStart: (messageId: string, data: any) => void
  handleToolEnd: (messageId: string, data: any) => void
  processChunk: (chunk: any, messageId: string) => Promise<void>
}

interface StreamEventHandlers {
  handleTitleUpdate: (data: any) => void
  handleSessionRefresh: (data: any) => Promise<void>
  handleStatusUpdate: (data: any, userMessageId: string) => void
  handleAiMessageId: (data: any, botMessageId: string) => string | null
  handleKeyword: (data: any) => void
  handleToolEvent: (data: any, messageId: string) => void
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
  updateMessageStatus,
  updateMessageId,
  addImageMessage,
  handleToolStart,
  handleToolEnd,
  processChunk
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
   * Handle message status update.
   * 
   * Updates user message status based on server events.
   */
  const handleStatusUpdate = useCallback((data: any, userMessageId: string) => {
    if (data.status === 'sent') {
      updateMessageStatus(userMessageId, MessageStatus.SENT)
    } else if (data.status === 'read') {
      updateMessageStatus(userMessageId, MessageStatus.READ)
    } else if (data.status === 'error') {
      console.error('[EventHandlers] Message error:', data.error)
      updateMessageStatus(userMessageId, MessageStatus.ERROR)
    }
  }, [updateMessageStatus])

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
      return newAiMessageId
    }
    return null
  }, [updateMessageId])

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
   * Handle tool-related events.
   * 
   * Routes tool events to appropriate handlers.
   */
  const handleToolEvent = useCallback((data: any, messageId: string) => {
    if (data.type === 'NAGISA_IS_USING_TOOL') {
      handleToolStart(messageId, data)
    } else if (data.type === 'NAGISA_TOOL_USE_CONCLUDED') {
      handleToolEnd(messageId, data)
    }
  }, [handleToolStart, handleToolEnd])

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
    handleStatusUpdate,
    handleAiMessageId,
    handleKeyword,
    handleToolEvent,
    handleContentUpdate
  }
}