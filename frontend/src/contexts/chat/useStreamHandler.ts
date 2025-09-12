import { useCallback } from 'react'
import { useMessageStateManager } from './useMessageStateManager'
import { useChunkProcessor } from './useChunkProcessor'
import { useStreamEventHandlers } from './useStreamEventHandlers'
import { useStreamProcessor } from './useStreamProcessor'

interface UseStreamHandlerProps {
  ttsEnabled: boolean
  currentSessionId: string | null
  processAudioData: (audioData: string, count: number) => Promise<boolean>
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

interface StreamHandlerOptions {
  userMessageId: string
  botMessageId: string
}

// Import Message type
import { Message } from '../../types/chat'

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
  ttsEnabled,
  currentSessionId,
  processAudioData,
  sessionRefreshSessions,
  sessionSwitchSession,
  setMessages
}: UseStreamHandlerProps) => {
  
  // Initialize message state manager
  const {
    updateMessageId,
    updateMessageText,
    finalizeMessage,
    addImageMessage
  } = useMessageStateManager({
    setMessages
  })
  
  // Initialize chunk processor
  const {
    processChunk,
    resetProcessor
  } = useChunkProcessor({
    ttsEnabled,
    processAudioData,
    updateMessageText,
    finalizeMessage
  })
  
  // Initialize event handlers
  const {
    handleTitleUpdate,
    handleSessionRefresh,
    handleStatusUpdate,
    handleAiMessageId,
    handleKeyword,
    handleContentUpdate
  } = useStreamEventHandlers({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession,
      updateMessageId,
    addImageMessage,
    processChunk
  })
  
  // Initialize stream processor
  const {
    processStream
  } = useStreamProcessor({
    handleTitleUpdate,
    handleSessionRefresh,
    handleStatusUpdate,
    handleAiMessageId,
    handleKeyword,
    handleContentUpdate,
    sessionRefreshSessions,
    finalizeMessage,
    resetProcessor
  })
  
  /**
   * Main stream response processing function.
   * 
   * Entry point for processing SSE stream responses.
   * Delegates to specialized processors for handling.
   */
  const processStreamResponse = useCallback(async (
    response: Response, 
    options: StreamHandlerOptions
  ) => {
    try {
      await processStream(response, options)
    } catch (error) {
      console.error('[StreamHandler] Stream processing failed:', error)
      throw error
    }
  }, [processStream])
  
  return {
    processStreamResponse
  }
}