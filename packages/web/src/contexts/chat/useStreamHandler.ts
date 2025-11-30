import { useCallback } from 'react'
import { useMessageStateManager } from './useMessageStateManager'
import { useChunkProcessor } from './useChunkProcessor'
import { useStreamEventHandlers } from './useStreamEventHandlers'
import { useStreamProcessor } from './useStreamProcessor'

interface UseStreamHandlerProps {
  currentSessionId: string | null
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

interface StreamHandlerOptions {
  userMessageId: string
  botMessageId: string
}

// Import Message type
import { Message } from '@toyoura-nagisa/core'

/**
 * Refactored stream handler using modular hooks.
 * 
 * Orchestrates stream processing by composing specialized hooks
 * for message state, chunk processing, and event handling.
 * 
 * Architecture:
 * - useMessageStateManager: Manages message state updates
 * - useChunkProcessor: Processes text/audio chunks
 * - useStreamEventHandlers: Handles various stream events
 * - useStreamProcessor: Core stream reading and parsing
 */
export const useStreamHandler = ({
  currentSessionId,
  sessionRefreshSessions,
  sessionSwitchSession,
  setMessages
}: UseStreamHandlerProps) => {
  
  // Initialize message state manager
  const {
    updateMessageId,
    addImageMessage
  } = useMessageStateManager({
    setMessages
  })

  // Initialize event handlers for SSE metadata events
  const {
    handleTitleUpdate,
    handleSessionRefresh,
    handleKeyword,
    handleContentUpdate
  } = useStreamEventHandlers({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession,
    updateMessageId,
    addImageMessage
  })
  
  // Initialize stream processor for SSE metadata events
  const {
    processStream
  } = useStreamProcessor({
    handleTitleUpdate,
    handleSessionRefresh,
    handleKeyword,
    handleContentUpdate,
    sessionRefreshSessions
  })
  
  /**
   * Main stream response processing function.
   *
   * Entry point for processing SSE stream responses.
   * Now only handles metadata events (title updates, session refreshes, keywords).
   * All content processing moved to WebSocket.
   */
  const processStreamResponse = useCallback(async (
    response: Response,
    options: StreamHandlerOptions
  ) => {
    try {
      await processStream(response, options)
    } catch (error) {
      throw error
    } finally {
      // SSE stream completed - content handled via WebSocket
    }
  }, [processStream])
  
  return {
    processStreamResponse
  }
}