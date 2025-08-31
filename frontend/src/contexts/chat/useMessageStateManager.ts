import { useCallback } from 'react'
import { Message } from '../../types/chat'

interface UseMessageStateManagerProps {
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>
}

interface MessageStateManager {
  updateMessageId: (oldId: string, newId: string) => void
  updateMessageText: (messageId: string, text: string, options?: {
    newText?: string
    streaming?: boolean
    isLoading?: boolean
    onRenderComplete?: () => void
  }) => void
  updateMessageToolState: (messageId: string, toolState: any) => void
  finalizeMessage: (messageId: string) => void
  addImageMessage: (imageData: any) => void
}

/**
 * Hook for managing message state updates during stream processing.
 * 
 * Handles message ID transitions, text updates, tool states, and finalization.
 * Extracted from useStreamHandler to improve separation of concerns.
 */
export const useMessageStateManager = ({
  setMessages
}: UseMessageStateManagerProps): MessageStateManager => {

  /**
   * Update message ID when server provides the final ID.
   * 
   * Transitions from temporary client-side ID to server-assigned ID.
   */
  const updateMessageId = useCallback((oldId: string, newId: string) => {
    console.log(`[MessageStateManager] Updating message ID: ${oldId} -> ${newId}`)
    
    setMessages(prev => 
      prev.map(msg => {
        if (msg.id === oldId) {
          console.log(`[MessageStateManager] Found and updated message: ${oldId} -> ${newId}`)
          // 保持所有现有状态，只更新ID
          return { 
            ...msg, 
            id: newId,
            // 保持streaming和text状态
            streaming: msg.streaming,
            text: msg.text,
            isLoading: msg.isLoading,
            newText: msg.newText
          }
        }
        return msg
      })
    )
  }, [setMessages])

  /**
   * Update message text content with streaming support.
   * 
   * Handles incremental text updates with rendering callbacks.
   */
  const updateMessageText = useCallback((
    messageId: string, 
    text: string,
    options?: {
      newText?: string
      streaming?: boolean
      isLoading?: boolean
      onRenderComplete?: () => void
    }
  ) => {
    console.log('[MessageStateManager] updateMessageText called:', {
      messageId,
      textLength: text?.length,
      textContent: text,
      options
    })
    
    setMessages(prev => {
      let messageFound = false
      const updatedMessages = prev.map(msg => {
        if (msg.id === messageId) {
          messageFound = true
          console.log('[MessageStateManager] Updating message text:', {
            messageId,
            oldText: msg.text,
            newText: text,
            options
          })
          return {
            ...msg,
            text,
            ...options
          }
        }
        return msg
      })
      
      if (!messageFound) {
        console.warn(`[MessageStateManager] Message not found with ID: ${messageId}`, {
          availableIds: prev.map(m => m.id)
        })
      }
      
      return updatedMessages
    })
  }, [setMessages])

  /**
   * Update message tool state.
   * 
   * Tracks tool usage status for UI display.
   */
  const updateMessageToolState = useCallback((messageId: string, toolState: any) => {
    setMessages(prev => 
      prev.map(msg => {
        if (msg.id === messageId) {
          return {
            ...msg,
            toolState
          }
        }
        return msg
      })
    )
  }, [setMessages])

  /**
   * Finalize message after stream completion.
   * 
   * Cleans up streaming state and temporary fields.
   */
  const finalizeMessage = useCallback((messageId: string) => {
    setMessages(prev => 
      prev.map(msg => {
        if (msg.id === messageId) {
          const finalText = msg.text && typeof msg.text === 'string' ? msg.text : ''
          return {
            ...msg,
            text: finalText,
            streaming: false,
            isLoading: false,
            newText: undefined,
            onRenderComplete: undefined
          }
        }
        return msg
      })
    )
  }, [setMessages])

  /**
   * Add image message to conversation.
   * 
   * Creates properly formatted image message from server data.
   */
  const addImageMessage = useCallback((imageData: any) => {
    const imageMessage: Message = {
      id: imageData.id || imageData.message_id,
      sender: 'bot',
      text: imageData.content || '',
      timestamp: new Date(imageData.timestamp || Date.now()).getTime(),
      files: [{
        name: 'generated_image',
        type: 'image/png',
        data: `/api/images/${imageData.image_path}`
      }]
    }

    setMessages(prev => [...prev, imageMessage])
  }, [setMessages])

  return {
    updateMessageId,
    updateMessageText,
    updateMessageToolState,
    finalizeMessage,
    addImageMessage
  }
}