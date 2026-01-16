import { useCallback, useEffect } from 'react'

interface UseStreamEventHandlersProps {
  currentSessionId: string | null
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  addImageMessage: (imageData: any) => void
}

interface StreamEventHandlers {
  handleTitleUpdate: (data: any) => void
  handleSessionRefresh: (data: any) => Promise<void>
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
  addImageMessage
}: UseStreamEventHandlersProps): StreamEventHandlers => {

  const handleKeyword = useCallback((_data: any) => {
    // Keyword handling reserved for future UI features.
  }, [])

  // Listen to WebSocket emotion keyword events
  useEffect(() => {
    const handleEmotionKeyword = (event: Event) => {
      const customEvent = event as CustomEvent
      const data = customEvent.detail
      if (data && data.keyword) {
        handleKeyword(data)
      }
    }

    window.addEventListener('emotionKeyword', handleEmotionKeyword)

    return () => {
      window.removeEventListener('emotionKeyword', handleEmotionKeyword)
    }
  }, [handleKeyword])

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

  // Listen to WebSocket title update events
  useEffect(() => {
    const handleTitleUpdateEvent = (event: Event) => {
      const customEvent = event as CustomEvent
      const data = customEvent.detail
      if (data) {
        handleTitleUpdate(data)
      }
    }

    window.addEventListener('titleUpdate', handleTitleUpdateEvent)

    return () => {
      window.removeEventListener('titleUpdate', handleTitleUpdateEvent)
    }
  }, [handleTitleUpdate])

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
   * Handle content update - deprecated in WebSocket architecture.
   *
   * All content updates now handled via WebSocket MESSAGE_CREATE.
   */
  const handleContentUpdate = useCallback(async (_data: any, _messageId: string) => {
    // No longer process content via SSE - everything goes through WebSocket
  }, [])

  return {
    handleTitleUpdate,
    handleSessionRefresh,
    handleKeyword,
    handleContentUpdate
  }
}
