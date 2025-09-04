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
          title="Create new session"
          aria-label="Create new session"
        >
          <svg 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2.5" 
            strokeLinecap="round" 
            strokeLinejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19"></line>
            <line x1="5" y1="12" x2="19" y2="12"></line>
          </svg>
        </button>
      </div>
    </div>
  )
}

export default NewSessionActions