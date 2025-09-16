import { useCallback, useRef } from 'react'

interface UseStreamProcessorProps {
  handleTitleUpdate: (data: any) => void
  handleSessionRefresh: (data: any) => Promise<void>
  handleKeyword: (data: any) => void
  handleContentUpdate: (data: any, messageId: string) => Promise<void>
  sessionRefreshSessions: () => Promise<any>
}

interface StreamProcessor {
  processStream: (response: Response, options: {
    userMessageId: string
    botMessageId: string
  }) => Promise<void>
}

/**
 * Hook for processing SSE stream responses.
 * 
 * Handles stream reading, line parsing, and event dispatching.
 * Core stream processing logic extracted from useStreamHandler.
 */
export const useStreamProcessor = ({
  handleTitleUpdate,
  handleSessionRefresh,
  handleKeyword,
  handleContentUpdate,
  sessionRefreshSessions
}: UseStreamProcessorProps): StreamProcessor => {
  
  
  /**
   * Process a single line from the SSE stream.
   * 
   * Parses JSON data and routes to appropriate handlers.
   */
  const processLine = useCallback((
    line: string,
    userMessageId: string,
    botMessageId: string
  ) => {
    if (line.trim() === '') return
    
    if (line.startsWith('data: ')) {
      const jsonData = line.slice(6)
      
      try {
        const data = JSON.parse(jsonData)

        // Route to specific handlers based on event type
        if (data.type === 'TITLE_UPDATE') {
          handleTitleUpdate(data)
          return
        }
        
        if (data.type === 'SESSION_REFRESH') {
          handleSessionRefresh(data)
          return
        }
        
        // Status updates now handled via WebSocket, skip SSE status events
        if (data.status) {
          return
        }
        
        
        // Handle keyword/motion (doesn't need content processing)
        if (data.keyword) {
          handleKeyword(data)
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
  }, [
    handleTitleUpdate,
    handleSessionRefresh,
    handleKeyword,
    handleContentUpdate
  ])
  
  /**
   * Process the entire SSE stream.
   *
   * Reads stream, parses lines, and coordinates metadata event handling.
   */
  const processStream = useCallback(async (
    response: Response,
    options: {
      userMessageId: string
      botMessageId: string
    }
  ) => {
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
          
          // Refresh sessions
          sessionRefreshSessions()
          
          break
        }
        
        // Decode and buffer
        buffer += decoder.decode(value, { stream: true })
        
        // Split by double newline (SSE format)
        const lines = buffer.split('\n\n')
        buffer = lines.pop() || ''
        
        // Process each complete line
        for (const line of lines) {
          processLine(line, userMessageId, botMessageId)
        }
      }
    } catch (error) {
      console.error('[StreamProcessor] Stream processing error:', error)
      throw error
    } finally {
      reader.releaseLock()
    }
  }, [
    processLine,
    sessionRefreshSessions
  ])
  
  return {
    processStream
  }
}