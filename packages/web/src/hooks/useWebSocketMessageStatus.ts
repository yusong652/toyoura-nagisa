/**
 * Hook for handling WebSocket-based message status updates.
 * 
 * Listens to message status events from WebSocket and provides
 * a callback to update message status in the UI.
 * 
 * This replaces the SSE-based status updates for real-time
 * bidirectional communication.
 */

import { useEffect, useCallback } from 'react'
import { MessageStatus } from '@toyoura-nagisa/core'

interface MessageStatusEvent {
  messageId: string
  status: 'sending' | 'sent' | 'read' | 'error'
  errorMessage?: string
}

interface UseWebSocketMessageStatusProps {
  onStatusUpdate: (messageId: string, status: MessageStatus, errorMessage?: string) => void
}

/**
 * Maps WebSocket status strings to MessageStatus enum values.
 */
const mapWebSocketStatusToMessageStatus = (status: string): MessageStatus => {
  switch (status) {
    case 'sending':
      return MessageStatus.SENDING
    case 'sent':
      return MessageStatus.SENT
    case 'read':
      return MessageStatus.READ
    case 'error':
      return MessageStatus.ERROR
    default:
      console.warn(`Unknown message status: ${status}`)
      return MessageStatus.ERROR
  }
}

/**
 * Hook that subscribes to WebSocket message status updates.
 * 
 * @param onStatusUpdate - Callback to handle status updates
 * 
 * @example
 * ```typescript
 * useWebSocketMessageStatus({
 *   onStatusUpdate: (messageId, status, errorMessage) => {
 *     updateMessageStatus(messageId, status)
 *     if (errorMessage) {
 *       console.error(`Message ${messageId} error: ${errorMessage}`)
 *     }
 *   }
 * })
 * ```
 */
export const useWebSocketMessageStatus = ({
  onStatusUpdate
}: UseWebSocketMessageStatusProps): void => {
  
  const handleMessageStatusUpdate = useCallback((event: CustomEvent<MessageStatusEvent>) => {
    const { messageId, status, errorMessage } = event.detail
    
    if (!messageId || !status) {
      console.warn('Invalid message status update event:', event.detail)
      return
    }
    
    const messageStatus = mapWebSocketStatusToMessageStatus(status)
    onStatusUpdate(messageId, messageStatus, errorMessage)
  }, [onStatusUpdate])
  
  useEffect(() => {
    // Type assertion for custom event
    const typedHandler = handleMessageStatusUpdate as EventListener
    
    // Subscribe to message status updates from WebSocket
    window.addEventListener('messageStatusUpdate', typedHandler)
    
    return () => {
      window.removeEventListener('messageStatusUpdate', typedHandler)
    }
  }, [handleMessageStatusUpdate])
}

/**
 * Simplified hook that returns the latest message status update.
 * 
 * Useful for components that just need to display status without
 * managing the update logic.
 */
export const useLatestMessageStatus = () => {
  // This could be extended to maintain a map of message statuses
  // if needed for displaying multiple message statuses simultaneously
  
  // For now, keeping it simple as requested
  return null
}