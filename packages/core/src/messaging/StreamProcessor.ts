/**
 * StreamProcessor - Platform-agnostic SSE stream processing
 *
 * Handles SSE (Server-Sent Events) stream reading, line parsing, and event dispatching.
 * Core stream processing logic extracted from web's useStreamProcessor hook.
 *
 * Features:
 * - SSE format parsing (data: JSON lines)
 * - Event-based architecture for loose coupling
 * - Buffer management for incomplete lines
 * - Automatic error handling and recovery
 */

/**
 * Data structure for SSE events
 */
export interface StreamEvent {
  type: string
  [key: string]: any
}

/**
 * Callback functions for stream event handlers
 */
export interface StreamEventHandlers {
  onTitleUpdate?: (data: StreamEvent) => void
  onSessionRefresh?: (data: StreamEvent) => Promise<void>
  onKeyword?: (data: StreamEvent) => void
  onContentUpdate?: (data: StreamEvent, messageId: string) => Promise<void>
  onStreamComplete?: () => void
}

/**
 * Options for stream processing
 */
export interface StreamProcessorOptions {
  userMessageId: string
  botMessageId: string
}

/**
 * StreamProcessor - Pure stream processing logic
 *
 * Converts SSE response streams into parsed events.
 * Platform-agnostic design allows use in both browser and Node.js environments.
 */
export class StreamProcessor {
  private handlers: StreamEventHandlers

  /**
   * Create a new StreamProcessor
   *
   * @param handlers - Event handler callbacks
   */
  constructor(handlers: StreamEventHandlers) {
    this.handlers = handlers
  }

  /**
   * Process a single line from the SSE stream
   *
   * Parses JSON data and routes to appropriate handlers based on event type.
   *
   * @param line - Raw SSE line
   * @param userMessageId - ID of user message
   * @param botMessageId - ID of bot message
   */
  private processLine(
    line: string,
    userMessageId: string,
    botMessageId: string
  ): void {
    if (line.trim() === '') return

    if (line.startsWith('data: ')) {
      const jsonData = line.slice(6)

      try {
        const data = JSON.parse(jsonData) as StreamEvent

        // Route to specific handlers based on event type
        if (data.type === 'TITLE_UPDATE' && this.handlers.onTitleUpdate) {
          this.handlers.onTitleUpdate(data)
          return
        }

        if (data.type === 'SESSION_REFRESH' && this.handlers.onSessionRefresh) {
          this.handlers.onSessionRefresh(data)
          return
        }

        // Status updates now handled via WebSocket, skip SSE status events
        if (data.status) {
          return
        }

        // Handle keyword/motion (doesn't need content processing)
        if (data.keyword && this.handlers.onKeyword) {
          this.handlers.onKeyword(data)
          // Skip content update if this is only a keyword
          if (!data.text && !data.audio) {
            return
          }
        }

        // All content updates now handled via WebSocket
        // SSE no longer carries text or TTS content in the new architecture
      } catch (e) {
        console.error('[StreamProcessor] Error parsing response:', e)
      }
    }
  }

  /**
   * Process the entire SSE stream
   *
   * Reads stream, parses lines, and coordinates metadata event handling.
   * Uses ReadableStream API for platform compatibility.
   *
   * @param response - Fetch Response object with SSE stream
   * @param options - Processing options (message IDs)
   */
  async processStream(
    response: Response,
    options: StreamProcessorOptions
  ): Promise<void> {
    const { userMessageId, botMessageId } = options

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('Unable to read response stream')
    }

    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          // Wait for any pending chunk processing
          await new Promise(resolve => setTimeout(resolve, 100))

          // No longer need to finalize placeholder messages since real messages are created via WebSocket

          // Notify completion
          if (this.handlers.onStreamComplete) {
            this.handlers.onStreamComplete()
          }

          break
        }

        // Decode and buffer
        buffer += decoder.decode(value, { stream: true })

        // Split by double newline (SSE format)
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''

        // Process each complete line
        for (const line of lines) {
          this.processLine(line, userMessageId, botMessageId)
        }
      }
    } catch (error) {
      console.error('[StreamProcessor] Stream processing error:', error)
      throw error
    } finally {
      reader.releaseLock()
    }
  }
}
