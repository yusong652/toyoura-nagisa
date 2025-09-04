/**
 * NewSessionActions component for creating new chat sessions.
 * 
 * Provides an input field and button for users to create new
 * chat sessions with custom names.
 */

import React, { useState, useCallback } from 'react'
import { NewSessionActionsProps } from '../types'
import './NewSessionActions.css'

/**
 * Component for new session creation interface.
 * 
 * This component demonstrates:
 * - Controlled input with local state management
 * - Async operation handling with loading states
 * - Callback props pattern for parent communication
 * 
 * @param onCreateSession - Async callback to create session with name
 * @param isCreating - Whether creation is in progress
 */
const NewSessionActions: React.FC<NewSessionActionsProps> = ({ 
  onCreateSession, 
  isCreating 
}) => {
  // Local state for input value
  const [sessionName, setSessionName] = useState<string>('')
  
  /**
   * Handle session creation with local state reset.
   * Clears input after passing name to parent handler.
   */
  const handleCreate = useCallback(async () => {
    await onCreateSession(sessionName)
    setSessionName('') // Clear input after creation
  }, [sessionName, onCreateSession])
  
  /**
   * Handle Enter key press for convenient session creation.
   * Provides keyboard accessibility for power users.
   */
  const handleKeyPress = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !isCreating) {
      handleCreate()
    }
  }, [handleCreate, isCreating])
  
  return (
    <div className="chat-history-actions">
      <div className="new-session-input-container">
        <input
          type="text"
          placeholder="New Session Name"
          value={sessionName}
          onChange={(e) => setSessionName(e.target.value)}
          onKeyPress={handleKeyPress}
          className="new-session-input"
          disabled={isCreating}
        />
        <button 
          className="new-session-button"
          onClick={handleCreate}
          disabled={isCreating}
        >
          {isCreating ? 'Creating...' : 'New'}
        </button>
      </div>
    </div>
  )
}

export default NewSessionActions