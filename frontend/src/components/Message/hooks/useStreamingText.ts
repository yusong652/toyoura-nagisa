import { useState, useEffect } from 'react'
import { Message } from '../../../types/chat'
import { StreamingTextHookReturn } from '../types'

/**
 * Hook for managing streaming text display logic.
 * 
 * Handles incremental text updates, chunk management, and streaming animation
 * for bot messages with real-time content updates.
 * 
 * Args:
 *     message: Message object with streaming text properties
 * 
 * Returns:
 *     StreamingTextHookReturn: Object containing:
 *         - displayText: string - Current accumulated text
 *         - chunks: string[] - Array of text chunks for animation
 *         - setDisplayText: Function to manually update display text
 *         - setChunks: Function to manually update chunks
 */
export const useStreamingText = (message: Message): StreamingTextHookReturn => {
  const { text, newText, streaming, sender, onRenderComplete } = message
  
  const [displayText, setDisplayText] = useState('')
  const [chunks, setChunks] = useState<string[]>([])
  
  useEffect(() => {
    if (streaming && sender === 'bot') {
      if (newText) {
        // Incremental update with new text chunk
        setChunks(prev => [...prev, newText])
        setDisplayText(prev => prev + newText)
        // Notify render completion
        onRenderComplete?.()
      } else if (text) {
        // Handle case where newText is not available but text is updated
        setDisplayText(prev => {
          if (prev !== text) {
            // Add virtual chunk to prevent loading animation
            setChunks(current => current.length === 0 ? [''] : current)
            return text
          }
          return prev
        })
      }
    } else {
      // Non-streaming: directly set final text
      setDisplayText(text || '')
      setChunks([])
    }
  }, [text, newText, streaming, sender, onRenderComplete])
  
  return {
    displayText,
    chunks,
    setDisplayText,
    setChunks
  }
}