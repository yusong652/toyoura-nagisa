import { useCallback, useRef } from 'react'
import { MessageType, TTSChunkMessage } from '../../types/websocket'
import WebSocketManager from '../../utils/websocket-manager'

interface WebSocketTTSProps {
  ttsEnabled: boolean
  processAudioData: (audioData: string, count: number) => Promise<boolean>
  updateMessageText: (messageId: string, text: string, options?: any) => void
  finalizeMessage: (messageId: string) => void
  websocketManager?: WebSocketManager
}

interface ChunkData {
  text?: string
  audio?: string
  index?: number
}

interface WebSocketTTSHandler {
  setupTTSHandler: (messageId: string) => void
  cleanupTTSHandler: () => void
  resetTTSProcessor: () => void
  updateMessageId: (oldId: string, newId: string) => void
}

/**
 * Hook for processing TTS chunks from WebSocket messages.
 *
 * Replaces SSE-based TTS processing with real-time WebSocket handling.
 * Maintains compatibility with existing chunk processor interface.
 */
export const useWebSocketTTS = ({
  ttsEnabled,
  processAudioData,
  updateMessageText,
  finalizeMessage,
  websocketManager
}: WebSocketTTSProps): WebSocketTTSHandler => {

  // Processing state
  const isProcessingRef = useRef(false)
  const chunkQueueRef = useRef<ChunkData[]>([])
  const chunkBufferRef = useRef<Map<number, ChunkData>>(new Map())
  const expectedIndexRef = useRef(0)
  const audioCountRef = useRef(0)
  const currentMessageRef = useRef<string>('')
  const currentMessageIdRef = useRef<string>('')
  const activeMessageIdsRef = useRef<Set<string>>(new Set())

  // Store reference to the TTS message handler for cleanup
  const ttsMessageHandlerRef = useRef<((message: any) => void) | null>(null)

  // WebSocket message handler
  const handleTTSMessage = useCallback(async (message: TTSChunkMessage) => {
    // Check if we have any active message IDs to process
    const activeIds = Array.from(activeMessageIdsRef.current)
    const messageId = currentMessageIdRef.current

    console.log('[WebSocketTTS] Received TTS chunk:', {
      activeIds,
      currentMessageId: messageId,
      messageSessionId: message.session_id,
      hasText: message.text !== undefined,
      textContent: message.text,
      hasAudio: message.audio !== undefined,
      index: message.index,
      engineStatus: message.engine_status,
      error: message.error
    })

    if (!messageId && activeIds.length === 0) {
      console.warn('[WebSocketTTS] Received TTS chunk without active message ID, ignoring')
      return
    }

    // Use current message ID or the most recent active ID
    const targetMessageId = messageId || activeIds[activeIds.length - 1]

    // Convert WebSocket message to chunk format
    const chunkData: ChunkData = {
      text: message.text,
      audio: message.audio,
      index: message.index
    }

    // Process the chunk using existing logic
    await processChunk(chunkData, targetMessageId)

    // Handle final chunk or errors
    if (message.is_final || message.error) {
      console.log('[WebSocketTTS] Final TTS chunk or error received:', {
        isFinal: message.is_final,
        error: message.error,
        targetMessageId
      })

      // Small delay to ensure all processing completes
      setTimeout(() => {
        if (!isProcessingRef.current && chunkQueueRef.current.length === 0) {
          finalizeMessage(targetMessageId)
        }
      }, 100)
    }
  }, [processAudioData, updateMessageText, finalizeMessage, ttsEnabled])

  /**
   * Process a single chunk of text and/or audio.
   *
   * Handles text accumulation and audio playback sequentially.
   */
  const processSingleChunk = useCallback(async (
    chunk: ChunkData,
    messageId: string
  ): Promise<void> => {
    // Process text if present
    if (chunk.text !== undefined && chunk.text !== null) {
      const newText = chunk.text

      if (newText.length > 0) {
        currentMessageRef.current += newText

        // Update message text immediately
        if (!ttsEnabled) {
          updateMessageText(messageId, currentMessageRef.current, {
            streaming: true,
            isLoading: false
          })
        } else {
          updateMessageText(messageId, currentMessageRef.current, {
            newText,
            streaming: true,
            isLoading: false
          })
        }

        // Small delay for smooth rendering
        await new Promise(resolve => setTimeout(resolve, 10))
      }
    }

    // Process audio if TTS is enabled
    if (ttsEnabled && chunk.audio && typeof chunk.audio === 'string' && chunk.audio.length > 0) {
      try {
        await processAudioData(chunk.audio, audioCountRef.current++)
      } catch (error) {
        console.error('[WebSocketTTS] Audio processing failed:', error)
      }
    }
  }, [ttsEnabled, processAudioData, updateMessageText])

  /**
   * Process chunks from queue sequentially.
   *
   * Ensures chunks are processed in order when ordering is required.
   */
  const processQueuedChunks = useCallback(async (messageId: string): Promise<void> => {
    while (chunkQueueRef.current.length > 0) {
      const chunk = chunkQueueRef.current.shift()
      if (!chunk) break

      await processSingleChunk(chunk, messageId)
    }

    isProcessingRef.current = false
  }, [processSingleChunk])

  /**
   * Handle ordered chunk with index.
   *
   * Buffers out-of-order chunks and processes them sequentially.
   */
  const handleOrderedChunk = useCallback(async (
    chunk: ChunkData,
    messageId: string
  ): Promise<void> => {
    if (chunk.index === undefined) return

    const chunkIndex = chunk.index

    // Buffer the chunk
    chunkBufferRef.current.set(chunkIndex, chunk)

    // Process all sequential chunks available
    while (chunkBufferRef.current.has(expectedIndexRef.current)) {
      const bufferedChunk = chunkBufferRef.current.get(expectedIndexRef.current)!
      chunkBufferRef.current.delete(expectedIndexRef.current)

      chunkQueueRef.current.push(bufferedChunk)
      expectedIndexRef.current++

      if (!isProcessingRef.current) {
        isProcessingRef.current = true
        await processQueuedChunks(messageId)
      }
    }
  }, [processQueuedChunks])

  /**
   * Process chunk data (compatible with existing interface).
   */
  const processChunk = useCallback(async (
    chunk: ChunkData,
    messageId: string
  ): Promise<void> => {
    if (!chunk) return

    console.log('[WebSocketTTS] processChunk called:', {
      messageId,
      hasText: chunk.text !== undefined,
      textContent: chunk.text,
      hasAudio: chunk.audio !== undefined,
      hasIndex: chunk.index !== undefined,
      index: chunk.index
    })

    // All content chunks should be ordered (have index)
    if (chunk.index !== undefined && typeof chunk.index === 'number') {
      await handleOrderedChunk(chunk, messageId)
    } else if (chunk.text !== undefined || chunk.audio !== undefined) {
      // Log warning if we receive content without index (shouldn't happen)
      console.warn('[WebSocketTTS] Received content chunk without index, treating as ordered chunk #0')
      chunk.index = 0
      await handleOrderedChunk(chunk, messageId)
    } else {
      // Ignore chunks without content or index
    }
  }, [handleOrderedChunk])

  /**
   * Reset processor state for new stream.
   *
   * Clears all buffers and resets counters.
   */
  const resetTTSProcessor = useCallback(() => {
    isProcessingRef.current = false
    chunkQueueRef.current = []
    chunkBufferRef.current.clear()
    expectedIndexRef.current = 0
    audioCountRef.current = 0
    currentMessageRef.current = ''
  }, [])

  /**
   * Setup TTS message handler for specific message.
   */
  const setupTTSHandler = useCallback((messageId: string) => {
    console.log('[WebSocketTTS] Setting up TTS handler for message:', messageId, {
      hasExistingHandler: !!ttsMessageHandlerRef.current,
      hasWebSocketManager: !!websocketManager
    })

    // Add message ID to active set
    activeMessageIdsRef.current.add(messageId)
    currentMessageIdRef.current = messageId

    // Reset processor state
    resetTTSProcessor()

    // Always ensure we have a handler registered
    if (!ttsMessageHandlerRef.current && websocketManager) {
      // Create and store new handler
      const ttsHandler = (message: any) => {
        if (message.type === MessageType.TTS_CHUNK) {
          console.log('[WebSocketTTS] Raw WebSocket TTS message received:', message)
          handleTTSMessage(message as TTSChunkMessage)
        }
      }

      ttsMessageHandlerRef.current = ttsHandler

      // Add WebSocket message listener
      websocketManager.on('message', ttsHandler)
      console.log('[WebSocketTTS] WebSocket TTS handler registered')
    } else if (!websocketManager) {
      console.warn('[WebSocketTTS] No WebSocket manager available!')
    } else {
      console.log('[WebSocketTTS] TTS handler already exists, updating message ID only')
    }
  }, [websocketManager, handleTTSMessage, resetTTSProcessor])

  /**
   * Cleanup TTS handler.
   */
  const cleanupTTSHandler = useCallback(() => {
    console.log('[WebSocketTTS] Cleaning up TTS handler')

    // Clear current message ID but keep handler active for a bit
    currentMessageIdRef.current = ''

    // Don't immediately remove handler - keep it active for late-arriving TTS chunks
    // Use a delay to allow for any pending TTS chunks
    setTimeout(() => {
      console.log('[WebSocketTTS] Delayed cleanup - checking if we should remove handler')

      // Only remove if no active message IDs and no current message
      if (activeMessageIdsRef.current.size === 0 && !currentMessageIdRef.current) {
        if (ttsMessageHandlerRef.current && websocketManager) {
          websocketManager.removeListener('message', ttsMessageHandlerRef.current)
          ttsMessageHandlerRef.current = null
          console.log('[WebSocketTTS] WebSocket TTS handler removed')
        }
      } else {
        console.log('[WebSocketTTS] Keeping handler active, active messages:', Array.from(activeMessageIdsRef.current))
      }
    }, 2000) // 2 second delay to allow for late TTS chunks
  }, [websocketManager])

  /**
   * Update message ID when it changes during processing.
   */
  const updateMessageId = useCallback((oldId: string, newId: string) => {
    console.log('[WebSocketTTS] Updating message ID:', { oldId, newId })

    // Update active message IDs
    if (activeMessageIdsRef.current.has(oldId)) {
      activeMessageIdsRef.current.delete(oldId)
      activeMessageIdsRef.current.add(newId)
    }

    // Update current message ID if it matches
    if (currentMessageIdRef.current === oldId) {
      currentMessageIdRef.current = newId
    }
  }, [])

  return {
    setupTTSHandler,
    cleanupTTSHandler,
    resetTTSProcessor,
    updateMessageId
  }
}