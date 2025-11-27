/**
 * ChunkProcessor - Platform-agnostic chunk processing and ordering
 *
 * Handles text and audio chunks from stream with proper ordering and buffering.
 * Core chunk processing logic extracted from web's useChunkProcessor hook.
 *
 * Features:
 * - Chunk ordering and sequential processing
 * - Out-of-order chunk buffering
 * - Text accumulation and audio coordination
 * - Event-based architecture for loose coupling
 */

/**
 * Chunk data structure from stream
 */
export interface ChunkData {
  text?: string | string[]
  audio?: string
  index?: number
  next?: ChunkData
  keyword?: string
}

/**
 * Options for message updates
 */
export interface MessageUpdateOptions {
  streaming?: boolean
  isLoading?: boolean
  newText?: string
}

/**
 * Callback functions for chunk event handlers
 */
export interface ChunkEventHandlers {
  onTextUpdate: (messageId: string, text: string, options?: MessageUpdateOptions) => void
  onAudioChunk?: (audioData: string, count: number) => Promise<boolean>
  onMessageFinalize: (messageId: string) => void
}

/**
 * ChunkProcessor - Pure chunk processing logic
 *
 * Manages chunk ordering, buffering, and sequential processing.
 * Platform-agnostic design allows use in both browser and Node.js environments.
 */
export class ChunkProcessor {
  private handlers: ChunkEventHandlers
  private ttsEnabled: boolean

  // Processing state
  private isProcessing: boolean = false
  private chunkQueue: ChunkData[] = []
  private chunkBuffer: Map<number, ChunkData> = new Map()
  private expectedIndex: number = 0
  private audioCount: number = 0
  private currentMessage: string = ''

  /**
   * Create a new ChunkProcessor
   *
   * @param handlers - Event handler callbacks
   * @param ttsEnabled - Whether TTS is enabled
   */
  constructor(handlers: ChunkEventHandlers, ttsEnabled: boolean = false) {
    this.handlers = handlers
    this.ttsEnabled = ttsEnabled
  }

  /**
   * Process a single chunk of text and/or audio
   *
   * Handles text accumulation and audio playback sequentially.
   *
   * @param chunk - Chunk data to process
   * @param messageId - ID of message being updated
   */
  private async processSingleChunk(
    chunk: ChunkData,
    messageId: string
  ): Promise<void> {
    // Process text if present
    if (chunk.text !== undefined && chunk.text !== null) {
      let newText = ''
      if (typeof chunk.text === 'string') {
        newText = chunk.text
      } else if (Array.isArray(chunk.text)) {
        newText = chunk.text.filter((t) => typeof t === 'string').join('')
      }

      if (newText.length > 0) {
        this.currentMessage += newText

        // Update message text immediately
        // When TTS is disabled, we pass the full text without newText to avoid duplication
        if (!this.ttsEnabled) {
          this.handlers.onTextUpdate(messageId, this.currentMessage, {
            streaming: true,
            isLoading: false
          })
        } else {
          this.handlers.onTextUpdate(messageId, this.currentMessage, {
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
    if (
      this.ttsEnabled &&
      this.handlers.onAudioChunk &&
      chunk.audio &&
      typeof chunk.audio === 'string' &&
      chunk.audio.length > 0
    ) {
      try {
        await this.handlers.onAudioChunk(chunk.audio, this.audioCount++)
      } catch (error) {
        console.error('[ChunkProcessor] Audio processing error:', error)
      }
    }
  }

  /**
   * Process chunks from queue sequentially
   *
   * Ensures chunks are processed in order when ordering is required.
   *
   * @param messageId - ID of message being updated
   */
  private async processQueuedChunks(messageId: string): Promise<void> {
    while (this.chunkQueue.length > 0) {
      const chunk = this.chunkQueue.shift()
      if (!chunk) break

      await this.processSingleChunk(chunk, messageId)

      // Process nested chunks if present
      if (chunk.next) {
        await this.processSingleChunk(chunk.next, messageId)
      }
    }

    this.isProcessing = false
  }

  /**
   * Handle ordered chunk with index
   *
   * Buffers out-of-order chunks and processes them sequentially.
   *
   * @param chunk - Chunk data with index
   * @param messageId - ID of message being updated
   */
  private async handleOrderedChunk(
    chunk: ChunkData,
    messageId: string
  ): Promise<void> {
    if (chunk.index === undefined) return

    const chunkIndex = chunk.index

    // Buffer the chunk
    this.chunkBuffer.set(chunkIndex, chunk)

    // Process all sequential chunks available
    while (this.chunkBuffer.has(this.expectedIndex)) {
      const bufferedChunk = this.chunkBuffer.get(this.expectedIndex)!
      this.chunkBuffer.delete(this.expectedIndex)

      this.chunkQueue.push(bufferedChunk)
      this.expectedIndex++

      if (!this.isProcessing) {
        this.isProcessing = true
        await this.processQueuedChunks(messageId)
      }
    }
  }

  /**
   * Main chunk processing entry point
   *
   * All text/audio chunks should have an index for ordered processing.
   * Chunks without index and without content are ignored.
   *
   * @param chunk - Chunk data to process
   * @param messageId - ID of message being updated
   */
  async processChunk(chunk: ChunkData, messageId: string): Promise<void> {
    if (!chunk) return

    // All content chunks should be ordered (have index)
    if (chunk.index !== undefined && typeof chunk.index === 'number') {
      await this.handleOrderedChunk(chunk, messageId)
    } else if (chunk.text !== undefined || chunk.audio !== undefined) {
      // Log warning if we receive content without index (shouldn't happen)
      console.warn('[ChunkProcessor] Received content chunk without index, assigning index 0')
      chunk.index = 0
      await this.handleOrderedChunk(chunk, messageId)
    } else {
      // Ignore chunks without content or index (e.g., keyword-only chunks)
    }

    // Check if processing is complete
    if (!this.isProcessing && this.chunkQueue.length === 0) {
      this.handlers.onMessageFinalize(messageId)
    }
  }

  /**
   * Reset processor state for new stream
   *
   * Clears all buffers and resets counters.
   */
  reset(): void {
    this.isProcessing = false
    this.chunkQueue = []
    this.chunkBuffer.clear()
    this.expectedIndex = 0
    this.audioCount = 0
    this.currentMessage = ''
  }

  /**
   * Get current accumulated message text
   *
   * @returns Current message text
   */
  getCurrentMessage(): string {
    return this.currentMessage
  }

  /**
   * Update TTS enabled state
   *
   * @param enabled - Whether TTS should be enabled
   */
  setTTSEnabled(enabled: boolean): void {
    this.ttsEnabled = enabled
  }
}
