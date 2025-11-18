/**
 * Hook for handling streaming content updates from WebSocket.
 *
 * This hook listens for 'streamingUpdate' custom events dispatched by ConnectionContext
 * and updates message content arrays progressively. It ensures data structure consistency
 * between real-time streaming and session refresh.
 *
 * Design:
 * - Backend sends accumulated complete content blocks (not individual chunks)
 * - Frontend simply replaces message content array (no accumulation needed)
 * - Same data structure used for streaming and database storage
 *
 * @param setMessages - Message state setter from ChatContext
 */

import { useEffect } from 'react'
import { Message, TokenUsage, ContentBlock } from '../../types/chat'

interface StreamingUpdateDetail {
  messageId: string
  content: ContentBlock[]  // ContentBlock array from backend
  streaming: boolean
  usage?: TokenUsage  // Optional token usage statistics
}

interface UseStreamingUpdateHandlerProps {
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
  setIsLLMThinking?: (thinking: boolean) => void  // Callback to update global LLM thinking status
}

export const useStreamingUpdateHandler = ({ setMessages, setIsLLMThinking }: UseStreamingUpdateHandlerProps) => {
  useEffect(() => {
    const handleStreamingUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<StreamingUpdateDetail>
      const { messageId, content, streaming, usage } = customEvent.detail

      setMessages(prev => prev.map(msg => {
        if (msg.id === messageId) {
          return {
            ...msg,
            content,           // Replace content array with accumulated blocks
            streaming,         // Update streaming flag
            text: '',          // Clear text field (content takes priority)
            usage              // Add token usage statistics (may be undefined)
          }
        }
        return msg
      }))

      // Update thinking status based on backend's streaming flag
      // Backend sends streaming=false only when all work (including tool execution) is complete
      if (!streaming) {
        setIsLLMThinking?.(false)
      }
    }

    // Listen for streaming update events from ConnectionContext
    window.addEventListener('streamingUpdate', handleStreamingUpdate)

    return () => {
      window.removeEventListener('streamingUpdate', handleStreamingUpdate)
    }
  }, [setMessages, setIsLLMThinking])
}

export default useStreamingUpdateHandler
