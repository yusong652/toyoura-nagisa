/**
 * SessionItem component for individual chat session display.
 * 
 * Renders a single chat session with title, date, and delete button.
 * Supports active state highlighting and click interactions.
 */

import React, { useCallback } from 'react'
import { SessionItemProps } from '../types'
import './SessionItem.css'

/**
 * Format date string for display.
 * Uses browser's locale for automatic localization.
 * 
 * @param date - ISO date string to format
 * @returns Formatted date string in user's locale
 */
const formatDate = (date: string): string => {
  return new Date(date).toLocaleString()
}

/**
 * Individual session item component.
 * 
 * This component demonstrates:
 * - Event handling with stopPropagation for nested interactions
 * - Conditional CSS classes for active state
 * - Date formatting utilities
 * - Async event handling for deletion
 * 
 * @param session - Chat session data object
 * @param isActive - Whether this session is currently active
 * @param onSelect - Callback when session is clicked
 * @param onDelete - Async callback for deletion with event
 */
const SessionItem: React.FC<SessionItemProps> = ({
  session,
  isActive,
  onSelect,
  onDelete
}) => {
  /**
   * Handle delete with event propagation control.
   * Prevents triggering session selection when deleting.
   */
  const handleDelete = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation() // Prevent parent click handler
    await onDelete(e)
  }, [onDelete])
  
  return (
    <div 
      className={`chat-history-item ${isActive ? 'active' : ''}`}
      onClick={onSelect}
    >
      <div className="chat-history-item-content">
        <div className="chat-history-item-title">{session.name}</div>
        <div className="chat-history-item-preview">
          {formatDate(session.updated_at)}
        </div>
      </div>
      <button 
        className="delete-session-button"
        onClick={handleDelete}
        aria-label={`Delete session: ${session.name}`}
        title="Delete session"
      >
        <svg 
          width="18" 
          height="18" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
        >
          <path d="M3 6h18" />
          <path d="M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2" />
          <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6" />
          <line x1="10" y1="11" x2="10" y2="17" />
          <line x1="14" y1="11" x2="14" y2="17" />
        </svg>
      </button>
    </div>
  )
}

export default SessionItem