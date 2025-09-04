/**
 * SessionList component for displaying chat sessions.
 * 
 * Renders a scrollable list of chat sessions with selection
 * and deletion capabilities.
 */

import React from 'react'
import { SessionListProps } from '../types'
import SessionItem from './SessionItem'
import './SessionList.css'

/**
 * Component to display list of chat sessions.
 * 
 * This component demonstrates:
 * - Conditional rendering (empty state vs session list)
 * - List rendering with key prop best practices
 * - Component composition with SessionItem
 * 
 * @param sessions - Array of chat sessions to display
 * @param currentSessionId - ID of active session for highlighting
 * @param onSwitchSession - Callback to switch sessions
 * @param onDeleteSession - Async callback to delete sessions
 */
const SessionList: React.FC<SessionListProps> = ({
  sessions,
  currentSessionId,
  onSwitchSession,
  onDeleteSession
}) => {
  // Empty state when no sessions exist
  if (sessions.length === 0) {
    return (
      <div className="chat-history-list">
        <div className="no-sessions-message">No chat history</div>
      </div>
    )
  }
  
  return (
    <div className="chat-history-list">
      {sessions.map((session) => (
        <SessionItem
          key={session.id}
          session={session}
          isActive={currentSessionId === session.id}
          onSelect={() => onSwitchSession(session.id)}
          onDelete={(e) => onDeleteSession(e, session.id)}
        />
      ))}
    </div>
  )
}

export default SessionList