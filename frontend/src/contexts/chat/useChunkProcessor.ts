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
        
        // Create render promise for smooth UI updates
        const renderPromise = new Promise<void>((resolve) => {
          updateMessageText(messageId, currentMessageRef.current, {
            newText,
            streaming: true,
            isLoading: currentMessageRef.current.length < 10,
            onRenderComplete: resolve
          })
        })

        await renderPromise
        await new Promise(resolve => setTimeout(resolve, 10))
      }
    }

    // Process audio if TTS is enabled
    if (ttsEnabled && chunk.audio && typeof chunk.audio === 'string' && chunk.audio.length > 0) {
      try {
        console.log(`[ChunkProcessor] Processing audio #${audioCountRef.current}`)
        await processAudioData(chunk.audio, audioCountRef.current++)
        console.log(`[ChunkProcessor] Audio #${audioCountRef.current - 1} completed`)
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
    
    console.log(`[ChunkProcessor] Buffered chunk #${chunkIndex}, expecting #${expectedIndexRef.current}`)
    
    // Process all sequential chunks available
    while (chunkBufferRef.current.has(expectedIndexRef.current)) {
      const bufferedChunk = chunkBufferRef.current.get(expectedIndexRef.current)!
      chunkBufferRef.current.delete(expectedIndexRef.current)
      
      console.log(`[ChunkProcessor] Processing ordered chunk #${expectedIndexRef.current}`)
      
      chunkQueueRef.current.push(bufferedChunk)
      expectedIndexRef.current++
      
      if (!isProcessingRef.current) {
        isProcessingRef.current = true
        await processQueuedChunks(messageId)
      }
    }
  }, [processQueuedChunks])

  /**
   * Handle unordered chunk (legacy format).
   * 
   * Processes chunks immediately without ordering.
   */
  const handleUnorderedChunk = useCallback(async (
    chunk: ChunkData,
    messageId: string
  ): Promise<void> => {
    chunkQueueRef.current.push(chunk)
    
    if (!isProcessingRef.current) {
      console.log('[ChunkProcessor] Processing unordered chunk')
      isProcessingRef.current = true
      await processQueuedChunks(messageId)
    }
  }, [processQueuedChunks])

  /**
   * Main chunk processing entry point.
   * 
   * Routes chunks to ordered or unordered processing based on presence of index.
   */
  const processChunk = useCallback(async (
    chunk: ChunkData,
    messageId: string
  ): Promise<void> => {
    if (!chunk) return
    
    console.log('[ChunkProcessor] Processing chunk:', chunk)
    
    if (chunk.index !== undefined && typeof chunk.index === 'number') {
      await handleOrderedChunk(chunk, messageId)
    } else {
      await handleUnorderedChunk(chunk, messageId)
    }
    
    // Check if processing is complete
    if (!isProcessingRef.current && chunkQueueRef.current.length === 0) {
      console.log('[ChunkProcessor] All chunks processed, finalizing message')
      finalizeMessage(messageId)
    }
  }, [handleOrderedChunk, handleUnorderedChunk, finalizeMessage])

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
    console.log('[ChunkProcessor] Processor reset')
  }, [])

  return {
    processChunk,
    resetProcessor
  }
}