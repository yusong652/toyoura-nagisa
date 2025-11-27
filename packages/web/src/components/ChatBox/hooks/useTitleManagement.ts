/**
 * Custom hook for managing ChatBox title and refresh functionality.
 * 
 * Demonstrates async operations in hooks and computed state management
 * with TypeScript's type safety features.
 */

import { useState, useMemo } from 'react'
import { Message } from '@aiNagisa/core'
import { useSession } from '../../../contexts/session/SessionContext'
import { UseTitleManagementReturn } from '../types'

/**
 * Manages session title display and refresh operations.
 * 
 * This hook encapsulates the logic for:
 * - Computing current session title
 * - Determining if title refresh is allowed
 * - Handling async title refresh with loading state
 * 
 * Args:
 *     messages: Array of messages to check refresh eligibility
 * 
 * Returns:
 *     UseTitleManagementReturn: Object containing:
 *         - currentSessionTitle: Displayed title string
 *         - isRefreshingTitle: Loading state boolean
 *         - canRefreshTitle: Computed permission boolean
 *         - handleRefreshTitle: Async refresh handler
 * 
 * TypeScript Learning Points:
 * - async/await in React hooks with proper typing
 * - useMemo for computed values with dependency arrays
 * - Error handling in async functions
 * - Boolean state management
 */
export const useTitleManagement = (
  messages: Message[]
): UseTitleManagementReturn => {
  // Get session context data
  const { sessions, currentSessionId, refreshTitle } = useSession()
  
  // Local loading state with explicit boolean type
  const [isRefreshingTitle, setIsRefreshingTitle] = useState<boolean>(false)
  
  // Compute current session title with fallback
  const currentSessionTitle = useMemo(() => {
    const session = sessions.find(s => s.id === currentSessionId)
    return session?.name || 'New Chat'
  }, [sessions, currentSessionId])
  
  // Compute if refresh is allowed based on message conditions
  const canRefreshTitle = useMemo(() => {
    // Need at least 2 messages
    const hasEnoughMessages = messages.length >= 2

    // Need both user and assistant messages
    const hasUserMessage = messages.some(msg => msg.role === 'user')
    const hasAssistantMessage = messages.some(msg => msg.role === 'assistant')

    return hasEnoughMessages && hasUserMessage && hasAssistantMessage
  }, [messages])
  
  // Async handler for title refresh
  const handleRefreshTitle = async (): Promise<void> => {
    // Guard conditions
    if (!currentSessionId || isRefreshingTitle || !canRefreshTitle) {
      return
    }
    
    try {
      setIsRefreshingTitle(true)
      await refreshTitle(currentSessionId)
    } catch (error) {
      // Type guard for error handling
      console.error('刷新标题失败:', error)
      // Could add error state here for UI feedback
    } finally {
      // Always reset loading state
      setIsRefreshingTitle(false)
    }
  }
  
  return {
    currentSessionTitle,
    currentSessionId,
    isRefreshingTitle,
    canRefreshTitle,
    handleRefreshTitle
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Async Function Types:
 *    () => Promise<void> - Async functions return Promises
 * 
 * 2. useMemo with Type Inference:
 *    TypeScript infers return type from computation
 * 
 * 3. Array Methods with Type Safety:
 *    messages.some() knows msg type from array type
 * 
 * 4. Optional Chaining with Fallback:
 *    session?.name || 'New Chat' - Safe access with default
 * 
 * 5. Error Handling:
 *    try/catch/finally with proper typing
 * 
 * 6. Boolean Guards:
 *    Multiple conditions combined with type safety
 */