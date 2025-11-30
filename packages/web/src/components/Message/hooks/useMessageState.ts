import { useState, useEffect } from 'react'
import { Message } from '@toyoura-nagisa/core'
import { MessageStateHookReturn } from '../types'

/**
 * Hook for managing message display state.
 * 
 * Handles text display logic, loading animations, and selection state.
 * Extracted from MessageItem for better separation of concerns.
 * 
 * Args:
 *     message: Message object containing text, streaming, and other properties
 *     selectedMessageId: Currently selected message ID for comparison
 * 
 * Returns:
 *     MessageStateHookReturn: Object containing:
 *         - displayText: string - Current text to display
 *         - chunks: string[] - Text chunks for streaming animation
 *         - dotCount: number - Loading animation dot count
 *         - isSelected: boolean - Whether this message is selected
 */
export const useMessageState = (
  message: Message,
  selectedMessageId: string | null
): MessageStateHookReturn => {
  const { text, streaming, role, id, newText, onRenderComplete } = message
  
  const [displayText, setDisplayText] = useState('')
  const [chunks, setChunks] = useState<string[]>([])
  const [dotCount, setDotCount] = useState(0)
  
  const isSelected = id ? selectedMessageId === id : false
  
  // Handle text updates for streaming messages
  useEffect(() => {
    if (streaming && role === 'assistant') {
      if (newText) {
        // Incremental update with newText
        setChunks(prev => [...prev, newText])
        setDisplayText(prev => prev + newText)
        onRenderComplete?.()
      } else if (text) {
        // No newText but has text (TTS disabled case)
        setDisplayText(prev => {
          if (prev !== text) {
            // Set virtual chunk to avoid showing loading
            setChunks(current => current.length === 0 ? [''] : current)
            return text
          }
          return prev
        })
      }
    } else {
      // Non-streaming case, set text directly
      setDisplayText(text || '')
      setChunks([])
    }
  }, [text, newText, streaming, role, onRenderComplete])
  
  // Handle loading animation
  useEffect(() => {
    let timer: number
    if (message.isLoading || (streaming && role === 'assistant' && chunks.length === 0)) {
      timer = window.setInterval(() => {
        setDotCount(prev => (prev % 3) + 1)
      }, 500)
    }
    return () => {
      if (timer) {
        window.clearInterval(timer)
      }
    }
  }, [message.isLoading, streaming, role, chunks.length])
  
  return {
    displayText,
    chunks,
    dotCount,
    isSelected
  }
}