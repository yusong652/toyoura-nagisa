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
import { Message } from '../../types/chat'

interface StreamingUpdateDetail {
  messageId: string
  content: Array<Record<string, any>>  // ContentBlock array from backend
  streaming: boolean
}

interface UseStreamingUpdateHandlerProps {
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

export const useStreamingUpdateHandler = ({ setMessages }: UseStreamingUpdateHandlerProps) => {
  useEffect(() => {
    const handleStreamingUpdate = (event: Event) => {
      const customEvent = event as CustomEvent<StreamingUpdateDetail>
      const { messageId, content, streaming } = customEvent.detail

      console.log(`[StreamingUpdate] Updating message ${messageId}, streaming: ${streaming}`, content)

      setMessages(prev => prev.map(msg => {
        if (msg.id === messageId) {
          return {
            ...msg,
            content,           // Replace content array with accumulated blocks
            streaming,         // Update streaming flag
            text: ''           // Clear text field (content takes priority)
          }
        }
        return msg
      }))
    }

    // Listen for streaming update events from ConnectionContext
    window.addEventListener('streamingUpdate', handleStreamingUpdate)

    return () => {
      window.removeEventListener('streamingUpdate', handleStreamingUpdate)
    }
  }, [setMessages])
}

export default useStreamingUpdateHandler
