import { useCallback } from 'react'
import { MessageStatus } from '../../types/chat'
import { useMessageStateManager } from './useMessageStateManager'
import { useToolStateManager } from './useToolStateManager'
import { useChunkProcessor } from './useChunkProcessor'
import { useStreamEventHandlers } from './useStreamEventHandlers'
import { useStreamProcessor } from './useStreamProcessor'

interface UseStreamHandlerProps {
  ttsEnabled: boolean
  currentSessionId: string | null
  processAudioData: (audioData: string, count: number) => Promise<boolean>
  sessionRefreshSessions: () => Promise<any>
  sessionSwitchSession: (sessionId: string) => Promise<void>
  updateMessageStatus: (messageId: string, status: MessageStatus) => void
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setToolState: (state: any) => void
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
 * for message state, tool state, chunk processing, and event handling.
 * 
 * Architecture:
 * - useMessageStateManager: Manages message state updates
 * - useToolStateManager: Handles tool usage tracking
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
  updateMessageStatus,
  setMessages,
  setToolState
}: UseStreamHandlerProps) => {
  
  // Initialize message state manager
  const {
    updateMessageId,
    updateMessageText,
    updateMessageToolState,
    finalizeMessage,
    addImageMessage
  } = useMessageStateManager({
    setMessages
  })
  
  // Initialize tool state manager
  const {
    handleToolStart,
    handleToolEnd
  } = useToolStateManager({
    setToolState,
    updateMessageToolState
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
    handleToolEvent,
    handleContentUpdate
  } = useStreamEventHandlers({
    currentSessionId,
    sessionRefreshSessions,
    sessionSwitchSession,
    updateMessageStatus,
    updateMessageId,
    addImageMessage,
    handleToolStart,
    handleToolEnd,
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
    handleToolEvent,
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