import { useState, useCallback, useMemo } from 'react'
import { useChat } from '../../../contexts/chat/ChatContext'
import { FileData } from '../../../types/chat'
import { 
  MessageSendingHookReturn, 
  SendingStatus,
  MessageInputInfo,
  isValidMessageContent,
  DEFAULT_INPUT_CONFIG 
} from '../types'

/**
 * Custom hook for managing message sending logic.
 * 
 * This hook encapsulates all message sending operations including validation,
 * keyboard handling, send state management, and integration with the chat
 * context. It follows aiNagisa's clean architecture by isolating sending
 * concerns from input state and UI rendering.
 * 
 * Features:
 * - Message validation before sending
 * - Keyboard shortcut handling (Enter to send, Shift+Enter for newline)
 * - Send state tracking with detailed status
 * - Integration with ChatContext for actual message sending
 * - Input clearing after successful send
 * - Error handling and recovery
 * 
 * Args:
 *     messageInfo: MessageInputInfo - Current message and files state
 *     clearInput: Function to clear input after successful send
 *     textareaRef?: React.RefObject<HTMLTextAreaElement> - Optional ref for focus management
 * 
 * Returns:
 *     MessageSendingHookReturn: Complete message sending interface:
 *         - handleSendMessage: Function to send current message and files
 *         - handleKeyPress: Keyboard event handler for shortcuts
 *         - canSendMessage: boolean indicating if message can be sent
 *         - isSending: boolean indicating if send is in progress
 *         - sendingStatus: Detailed sending status with messages
 * 
 * TypeScript Learning Points:
 * - useState with discriminated union types for status
 * - useCallback with async functions and proper dependencies
 * - useMemo for derived boolean state calculations
 * - Error handling in async context with typed catch blocks
 * - Integration with external context hooks
 */
const useMessageSending = (
  messageInfo: MessageInputInfo,
  clearInput: () => void,
  textareaRef?: React.RefObject<HTMLTextAreaElement>,
  mentionedFiles: string[] = []
): MessageSendingHookReturn => {
  // Internal sending state
  const [sendingStatus, setSendingStatus] = useState<SendingStatus>({
    status: 'idle'
  })
  
  // External chat context
  const { sendMessage, isLoading } = useChat()
  
  // Derived state - whether message can be sent
  const canSendMessage = useMemo<boolean>(() => {
    return messageInfo.hasContent && 
           !isLoading && 
           sendingStatus.status !== 'sending' &&
           (messageInfo.content.trim().length > 0 || messageInfo.files.length > 0)
  }, [messageInfo, isLoading, sendingStatus.status])
  
  // Simple sending indicator
  const isSending = sendingStatus.status === 'sending'
  
  // Main send message handler
  const handleSendMessage = useCallback(async (): Promise<void> => {
    // Pre-flight validation
    if (!canSendMessage) {
      console.warn('Cannot send message: validation failed')
      return
    }
    
    // Validate message content
    if (!isValidMessageContent(messageInfo.content) && messageInfo.files.length === 0) {
      setSendingStatus({
        status: 'error',
        message: 'Message cannot be empty'
      })
      return
    }
    
    try {
      // Update status to sending
      setSendingStatus({ status: 'sending' })
      
      // Prepare message data
      const currentMessage = messageInfo.content
      const currentFiles = [...messageInfo.files]

      // Clear input immediately for better UX
      clearInput()
      
      // Reset textarea height if available
      if (textareaRef?.current) {
        textareaRef.current.style.height = 'auto'
      }
      
      // Send message through chat context (with mentioned files)
      await sendMessage(currentMessage, currentFiles, mentionedFiles)
      
      // Success state
      setSendingStatus({ status: 'success' })
      
      // Reset to idle after brief success indication
      setTimeout(() => {
        setSendingStatus({ status: 'idle' })
      }, 1000)
      
    } catch (error: any) {
      console.error('Error sending message:', error)
      
      // Error state with message
      setSendingStatus({
        status: 'error',
        message: error.message || 'Failed to send message'
      })
      
      // Reset to idle after error display
      setTimeout(() => {
        setSendingStatus({ status: 'idle' })
      }, 3000)
    }
  }, [canSendMessage, messageInfo, clearInput, sendMessage, textareaRef, mentionedFiles])
  
  // Keyboard event handler
  const handleKeyPress = useCallback(async (e: React.KeyboardEvent): Promise<void> => {
    // Handle Enter key for sending
    if (e.key === 'Enter') {
      if (!e.shiftKey) {
        // Enter without Shift = send message
        e.preventDefault()
        await handleSendMessage()
      } else {
        // Shift+Enter = new line (default textarea behavior)
        // No need to prevent default, let textarea handle it
      }
    }
    
    // Handle Escape key to cancel sending (if needed)
    if (e.key === 'Escape' && isSending) {
      setSendingStatus({ status: 'idle' })
      // Note: We can't actually cancel the send once it's started,
      // but we can reset the UI state
    }
  }, [handleSendMessage, isSending])
  
  return {
    handleSendMessage,
    handleKeyPress,
    canSendMessage,
    isSending,
    sendingStatus
  }
}

export default useMessageSending

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Discriminated Union for Status**:
 *    ```typescript
 *    const [sendingStatus, setSendingStatus] = useState<SendingStatus>({
 *      status: 'idle'
 *    })
 *    ```
 *    Union type enables different status states with optional messages
 * 
 * 2. **useMemo with Complex Boolean Logic**:
 *    ```typescript
 *    const canSendMessage = useMemo<boolean>(() => {
 *      return messageInfo.hasContent && 
 *             !isLoading && 
 *             sendingStatus.status !== 'sending'
 *    }, [messageInfo, isLoading, sendingStatus.status])
 *    ```
 *    Derived state calculation with proper dependency tracking
 * 
 * 3. **Async useCallback with Error Handling**:
 *    ```typescript
 *    const handleSendMessage = useCallback(async (): Promise<void> => {
 *      try {
 *        await sendMessage(currentMessage, currentFiles)
 *      } catch (error: any) {
 *        // Typed error handling
 *      }
 *    }, [dependencies])
 *    ```
 *    Async callbacks with proper Promise typing and error boundaries
 * 
 * 4. **Optional Ref Parameter**:
 *    ```typescript
 *    textareaRef?: React.RefObject<HTMLTextAreaElement>
 *    ```
 *    Optional ref for enhanced functionality without tight coupling
 * 
 * 5. **Event Handler with Keyboard Logic**:
 *    ```typescript
 *    const handleKeyPress = useCallback(async (e: React.KeyboardEvent): Promise<void> => {
 *      if (e.key === 'Enter' && !e.shiftKey) {
 *        e.preventDefault()
 *        await handleSendMessage()
 *      }
 *    }, [handleSendMessage])
 *    ```
 *    Complex keyboard event handling with modifier key detection
 * 
 * 6. **State Machine Pattern**:
 *    Status transitions: idle → sending → success/error → idle
 * 
 * Hook Design Benefits:
 * - **Status Management**: Clear sending state with user feedback
 * - **Validation Logic**: Centralized message validation
 * - **Error Recovery**: Automatic status reset with timeouts
 * - **Keyboard UX**: Standard keyboard shortcuts (Enter, Shift+Enter)
 * - **Context Integration**: Seamless chat context usage
 * - **Performance**: Optimized with useCallback and useMemo
 * 
 * State Machine Flow:
 * ```
 * idle → (user clicks send) → sending → (success) → success → idle
 *                                    → (error) → error → idle
 * ```
 * 
 * Error Handling Strategy:
 * - Pre-flight validation prevents unnecessary API calls
 * - Try-catch wraps all async operations
 * - User feedback provided through status messages
 * - Automatic recovery with timeout-based state reset
 * - Graceful degradation if context is unavailable
 * 
 * Integration Pattern:
 * ```typescript
 * const {
 *   handleSendMessage,
 *   handleKeyPress,
 *   canSendMessage,
 *   isSending,
 *   sendingStatus
 * } = useMessageSending(messageInfo, clearInput, textareaRef)
 * ```
 * 
 * This pattern isolates all sending complexity, making the main component
 * focus on UI orchestration rather than business logic details.
 */