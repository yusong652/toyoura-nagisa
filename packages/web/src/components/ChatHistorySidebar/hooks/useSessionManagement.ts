/**
 * Custom hook for managing chat session operations.
 * 
 * This hook encapsulates all session management logic including
 * creation, switching, and deletion of chat sessions.
 */

import { useState, useCallback } from 'react'
import { useSession } from '../../../contexts/session/SessionContext'
import { useErrorDisplay } from '../../../hooks/useErrorDisplay'
import { SessionManagementReturn } from '../types'

/**
 * Hook to manage chat session operations with error handling.
 * 
 * @param onSessionSwitch - Optional callback after session switch
 * @returns SessionManagementReturn object containing:
 *   - newSessionName: string - Current new session name input
 *   - setNewSessionName: (name: string) => void - Update session name input
 *   - isCreating: boolean - Session creation in progress
 *   - handleCreateSession: () => Promise<void> - Create new session
 *   - handleSwitchSession: (id: string) => void - Switch active session
 *   - handleDeleteSession: (e, id) => Promise<void> - Delete a session
 * 
 * @example
 * const {
 *   newSessionName,
 *   setNewSessionName,
 *   isCreating,
 *   handleCreateSession,
 *   handleSwitchSession,
 *   handleDeleteSession
 * } = useSessionManagement(() => closeSidebar())
 * 
 * Note:
 * Automatically generates timestamps for unnamed sessions using
 * Chinese locale formatting for consistency with the application.
 */
export const useSessionManagement = (
  onSessionSwitch?: () => void
): SessionManagementReturn => {
  // State: New session name input
  const [newSessionName, setNewSessionName] = useState<string>('')
  // State: Track session creation status
  const [isCreating, setIsCreating] = useState<boolean>(false)
  
  // Context: Session operations from SessionContext
  const {
    createNewSession,
    switchSession,
    deleteSession
  } = useSession()
  
  // Hook: Error display management
  const { showTemporaryError } = useErrorDisplay()
  
  /**
   * Create a new chat session with automatic naming.
   * Uses timestamp if no name provided for user convenience.
   */
  const handleCreateSession = useCallback(async (): Promise<void> => {
    console.log('Creating new session with name:', newSessionName)
    setIsCreating(true)
    
    try {
      console.log('Calling createNewSession...')
      // Generate timestamp-based default title if name is empty
      const defaultTitle = newSessionName.trim() || new Date().toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      })
      
      await createNewSession(defaultTitle)
      console.log('Session created successfully')
      setNewSessionName('') // Clear input after successful creation
    } catch (error) {
      console.error('Error creating session:', error)
      // Show user-friendly error message
      showTemporaryError('Failed to create new session. Please try again.', 4000)
    } finally {
      setIsCreating(false)
    }
  }, [newSessionName, createNewSession, showTemporaryError])
  
  /**
   * Switch to a different chat session.
   * Executes optional callback after switch (typically closes sidebar).
   */
  const handleSwitchSession = useCallback((sessionId: string): void => {
    switchSession(sessionId)
    onSessionSwitch?.() // Execute callback if provided
  }, [switchSession, onSessionSwitch])
  
  /**
   * Delete a chat session with confirmation.
   * Prevents event propagation to avoid triggering parent click handlers.
   */
  const handleDeleteSession = useCallback(async (
    e: React.MouseEvent,
    sessionId: string
  ): Promise<void> => {
    e.stopPropagation() // Prevent triggering session selection
    
    // Confirm deletion with user
    if (window.confirm('Are you sure you want to delete this session?')) {
      await deleteSession(sessionId)
    }
  }, [deleteSession])
  
  return {
    newSessionName,
    setNewSessionName,
    isCreating,
    handleCreateSession,
    handleSwitchSession,
    handleDeleteSession
  }
}