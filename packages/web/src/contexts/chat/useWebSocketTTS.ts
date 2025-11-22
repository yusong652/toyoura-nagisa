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
  setupTTSHandler: () => void
  cleanupTTSHandler: () => void
  resetTTSProcessor: () => void
  updateMessageId: (oldId: string, newId: string) => void
}

/**
 * Hook for processing TTS chunks from WebSocket events.
 *
 * Listens to custom WebSocket TTS events and processes them using existing
 * chunk processing logic. Maintains compatibility with SSE-based flow.
 */
export const useWebSocketTTS = ({
  ttsEnabled,
  processAudioData,
  updateMessageText,
  finalizeMessage
}: Omit<WebSocketTTSProps, 'websocketManager'>): WebSocketTTSHandler => {

  // Processing state
  const isProcessingRef = useRef(false)
  const chunkQueueRef = useRef<ChunkData[]>([])
  const chunkBufferRef = useRef<Map<number, ChunkData>>(new Map())
  const expectedIndexRef = useRef(0)
  const audioCountRef = useRef(0)
  const currentMessageRef = useRef<string>('')
  const currentMessageIdRef = useRef<string>('')
  const activeMessageIdsRef = useRef<Set<string>>(new Set())

  // Store reference to the TTS event handler for cleanup
  const ttsEventHandlerRef = useRef<EventListener | null>(null)

  // WebSocket TTS event handler
  const handleTTSEvent = useCallback(async (event: CustomEvent) => {
    const data = event.detail

    // Use message_id from TTS chunk data - no longer need pre-set message IDs
    const targetMessageId = data.message_id

    if (!targetMessageId) {
      return
    }

    // Convert WebSocket event data to chunk format
    const chunkData: ChunkData = {
      text: data.text,
      audio: data.audio,
      index: data.index
    }

    // Process the chunk using existing logic
    await processChunk(chunkData, targetMessageId)

    // Handle final chunk or errors
    if (data.is_final || data.error) {
      // Small delay to ensure all processing completes
      setTimeout(() => {
        if (!isProcessingRef.current && chunkQueueRef.current.length === 0) {
          finalizeMessage(targetMessageId)

          // Clean up TTS handler after processing final chunk
          setTimeout(() => {
            if (ttsEventHandlerRef.current) {
              window.removeEventListener('websocket-tts-chunk', ttsEventHandlerRef.current)
              ttsEventHandlerRef.current = null
            }
          }, 1000) // Additional delay to ensure all processing is done
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
    // Process text if present and not empty
    // Note: Backend sends empty text for streaming messages (text already displayed)
    if (chunk.text !== undefined && chunk.text !== null && chunk.text.length > 0) {
      const newText = chunk.text
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

    // Process audio if TTS is enabled
    // Audio is sent regardless of whether text is present (for streaming messages)
    if (ttsEnabled && chunk.audio && typeof chunk.audio === 'string' && chunk.audio.length > 0) {
      try {
        await processAudioData(chunk.audio, audioCountRef.current++)
      } catch (error) {
        // Silent fail for audio processing errors
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


    // All content chunks should be ordered (have index)
    if (chunk.index !== undefined && typeof chunk.index === 'number') {
      await handleOrderedChunk(chunk, messageId)
    } else if (chunk.text !== undefined || chunk.audio !== undefined) {
      // Log warning if we receive content without index (shouldn't happen)
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
   * Setup TTS event handler - simplified since we get message_id from chunks.
   */
  const setupTTSHandler = useCallback(() => {
    // Reset processor state
    resetTTSProcessor()

    // Setup event listener if not already done
    if (!ttsEventHandlerRef.current) {
      const eventHandler = (event: Event) => {
        handleTTSEvent(event as CustomEvent)
      }

      ttsEventHandlerRef.current = eventHandler
      window.addEventListener('websocket-tts-chunk', eventHandler)
    }
  }, [handleTTSEvent, resetTTSProcessor])

  /**
   * Cleanup TTS handler - backup cleanup for edge cases.
   */
  const cleanupTTSHandler = useCallback(() => {
    // Extended delay for backup cleanup in case final chunk cleanup doesn't work
    setTimeout(() => {
      if (ttsEventHandlerRef.current) {
        window.removeEventListener('websocket-tts-chunk', ttsEventHandlerRef.current)
        ttsEventHandlerRef.current = null
      }
    }, 10000) // 10 second delay as backup cleanup
  }, [])

  /**
   * Update message ID - no longer needed since IDs come from TTS chunks.
   */
  const updateMessageId = useCallback((oldId: string, newId: string) => {
    // No longer needed since message IDs are provided by TTS chunks
  }, [])

  return {
    setupTTSHandler,
    cleanupTTSHandler,
    resetTTSProcessor,
    updateMessageId
  }
}