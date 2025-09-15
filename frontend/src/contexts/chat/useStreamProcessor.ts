import { useCallback, useRef } from 'react'

interface UseStreamProcessorProps {
  handleTitleUpdate: (data: any) => void
  handleSessionRefresh: (data: any) => Promise<void>
  handleAiMessageId: (data: any, botMessageId: string) => string | null
  handleKeyword: (data: any) => void
  handleContentUpdate: (data: any, messageId: string) => Promise<void>
  sessionRefreshSessions: () => Promise<any>
  finalizeMessage: (messageId: string) => void
  resetProcessor: () => void
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
  handleAiMessageId,
  handleKeyword,
  handleToolEvent,
  handleContentUpdate,
  sessionRefreshSessions,
  finalizeMessage,
  resetProcessor
}: UseStreamProcessorProps): StreamProcessor => {
  
  // Track final AI message ID
  const finalAiMessageIdRef = useRef<string | null>(null)
  
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
        const currentMessageId = finalAiMessageIdRef.current || botMessageId
        
        // Debug: Log all received data
        console.log('[StreamProcessor] Received data from backend:', {
          type: data.type,
          hasText: data.text !== undefined,
          textContent: data.text,
          hasAudio: data.audio !== undefined,
          hasMessageId: data.message_id !== undefined,
          messageId: data.message_id,
          hasToolCall: data.tool_call !== undefined,
          fullData: data
        })
        
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
        
        // Handle AI message ID update
        if (data.message_id && !finalAiMessageIdRef.current) {
          const newId = handleAiMessageId(data, botMessageId)
          if (newId) {
            finalAiMessageIdRef.current = newId
          }
        }
        
        // Handle keyword/motion (doesn't need content processing)
        if (data.keyword) {
          handleKeyword(data)
          // Skip content update if this is only a keyword
          if (!data.text && !data.audio) {
            return
          }
        }
        
        // Handle content updates (text/audio)
        // Only process SSE content if there's actual content
        // TTS chunks are now handled via WebSocket, so skip audio processing in SSE
        if (data.text !== undefined) {
          // Process text-only content through SSE (audio handled via WebSocket)
          const contentWithoutAudio = { ...data }
          delete contentWithoutAudio.audio  // Remove audio to prevent double processing

          // Always use the most current message ID
          const messageIdForUpdate = finalAiMessageIdRef.current || botMessageId
          console.log('[StreamProcessor] Processing SSE text content (audio handled via WebSocket):', {
            hasText: data.text !== undefined,
            textLength: data.text?.length,
            messageId: messageIdForUpdate,
            originalBotId: botMessageId,
            finalId: finalAiMessageIdRef.current,
            removedAudio: data.audio !== undefined
          })
          handleContentUpdate(contentWithoutAudio, messageIdForUpdate)
        }
      } catch (e) {
        console.error('[StreamProcessor] Error parsing response:', e)
      }
    }
  }, [
    handleTitleUpdate,
    handleSessionRefresh,
      handleAiMessageId,
    handleKeyword,
    handleContentUpdate
  ])
  
  /**
   * Process the entire SSE stream.
   * 
   * Reads stream, parses lines, and coordinates event handling.
   */
  const processStream = useCallback(async (
    response: Response,
    options: {
      userMessageId: string
      botMessageId: string
    }
  ) => {
    const { userMessageId, botMessageId } = options
    
    // Reset state for new stream
    finalAiMessageIdRef.current = null
    resetProcessor()
    
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
          
          // Finalize the message
          const finalMessageId = finalAiMessageIdRef.current || botMessageId
          finalizeMessage(finalMessageId)
          
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
    resetProcessor,
    finalizeMessage,
    sessionRefreshSessions
  ])
  
  return {
    processStream
  }
}