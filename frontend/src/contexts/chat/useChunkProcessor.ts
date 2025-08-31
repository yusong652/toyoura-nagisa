import { useCallback, useRef } from 'react'

interface ChunkData {
  text?: string | string[]
  audio?: string
  index?: number
  next?: any
}

interface UseChunkProcessorProps {
  ttsEnabled: boolean
  processAudioData: (audioData: string, count: number) => Promise<boolean>
  updateMessageText: (messageId: string, text: string, options?: any) => void
  finalizeMessage: (messageId: string) => void
}

interface ChunkProcessor {
  processChunk: (chunk: ChunkData, messageId: string) => Promise<void>
  resetProcessor: () => void
}

/**
 * Hook for processing text and audio chunks from stream.
 * 
 * Manages chunk ordering, buffering, and sequential processing.
 * Extracted from useStreamHandler for better testability and reusability.
 */
export const useChunkProcessor = ({
  ttsEnabled,
  processAudioData,
  updateMessageText,
  finalizeMessage
}: UseChunkProcessorProps): ChunkProcessor => {
  
  // Processing state
  const isProcessingRef = useRef(false)
  const chunkQueueRef = useRef<ChunkData[]>([])
  const chunkBufferRef = useRef<Map<number, ChunkData>>(new Map())
  const expectedIndexRef = useRef(0)
  const audioCountRef = useRef(0)
  const currentMessageRef = useRef<string>('')

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
      let newText = ''
      if (typeof chunk.text === 'string') {
        newText = chunk.text
      } else if (Array.isArray(chunk.text)) {
        newText = chunk.text.filter((t) => typeof t === 'string').join('')
      }

      if (newText.length > 0) {
        currentMessageRef.current += newText
        
        // Update message text immediately
        // When TTS is disabled, we pass the full text without newText to avoid duplication
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
        console.error('[ChunkProcessor] Audio processing failed:', error)
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
      
      // Process nested chunks if present
      if (chunk.next) {
        await processSingleChunk(chunk.next, messageId)
      }
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
   * Main chunk processing entry point.
   * 
   * All text/audio chunks should have an index for ordered processing.
   * Chunks without index and without content are ignored.
   */
  const processChunk = useCallback(async (
    chunk: ChunkData,
    messageId: string
  ): Promise<void> => {
    if (!chunk) return
    
    console.log('[ChunkProcessor] processChunk called:', {
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
      console.warn('[ChunkProcessor] Received content chunk without index, treating as ordered chunk #0')
      chunk.index = 0
      await handleOrderedChunk(chunk, messageId)
    } else {
      // Ignore chunks without content or index (e.g., keyword-only chunks)
    }
    
    // Check if processing is complete
    if (!isProcessingRef.current && chunkQueueRef.current.length === 0) {
      finalizeMessage(messageId)
    }
  }, [handleOrderedChunk, finalizeMessage, ttsEnabled])

  /**
   * Reset processor state for new stream.
   * 
   * Clears all buffers and resets counters.
   */
  const resetProcessor = useCallback(() => {
    isProcessingRef.current = false
    chunkQueueRef.current = []
    chunkBufferRef.current.clear()
    expectedIndexRef.current = 0
    audioCountRef.current = 0
    currentMessageRef.current = ''
  }, [])

  return {
    processChunk,
    resetProcessor
  }
}