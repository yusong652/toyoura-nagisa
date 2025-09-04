/**
 * ChatHistorySidebar main component.
 * 
 * A comprehensive sidebar for managing chat session history with
 * creation, switching, and deletion capabilities. Uses modular
 * architecture for maintainability and reusability.
 */

import React from 'react'
import { useSession } from '../../contexts/session/SessionContext'
import UnifiedErrorDisplay from '../UnifiedErrorDisplay'
import { useErrorDisplay } from '../../hooks/useErrorDisplay'
import { useSidebarState } from './hooks/useSidebarState'
import { useSessionManagement } from './hooks/useSessionManagement'
import SidebarHeader from './header/SidebarHeader'
import NewSessionActions from './actions/NewSessionActions'
import SessionList from './list/SessionList'
import { ChatHistorySidebarProps } from './types'
import './ChatHistorySidebar.css'

/**
 * Main ChatHistorySidebar component with modular architecture.
 * 
 * This component demonstrates:
 * - Custom hook composition for state management
 * - Component decomposition into logical sub-components
 * - Clean separation of concerns
 * - Error handling with unified error display
 * 
 * Architecture Overview:
 * - Uses custom hooks for sidebar state and session management
 * - Delegates rendering to specialized sub-components
 * - Maintains single responsibility principle
 */
const ChatHistorySidebar: React.FC<ChatHistorySidebarProps> = () => {
  // Context: Session data from SessionContext
  const { sessions, currentSessionId } = useSession()
  
  // Hook: Error display management
  const { error, clearError } = useErrorDisplay()
  
  // Hook: Sidebar visibility state management with click outside
  const { isOpen, toggleSidebar, closeSidebar, sidebarRef, toggleRef } = useSidebarState()
  
  // Hook: Session CRUD operations with sidebar integration
  const {
    newSessionName,
    setNewSessionName,
    isCreating,
    handleCreateSession,
    handleSwitchSession,
    handleDeleteSession
  } = useSessionManagement(closeSidebar)
  
  /**
   * Wrapper for create session to pass name from child component.
   * Bridges NewSessionActions local state with session management hook.
   */
  const handleCreateWithName = async (name: string): Promise<void> => {
    setNewSessionName(name)
    await handleCreateSession()
  }
  
  return (
    <>
      {/* Toggle button - always visible */}
      <button 
        ref={toggleRef}
        className="history-toggle" 
        onClick={toggleSidebar} 
        aria-label="Toggle chat history"
      >
        <svg 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
        >
          <line x1="3" y1="12" x2="21" y2="12"></line>
          <line x1="3" y1="6" x2="21" y2="6"></line>
          <line x1="3" y1="18" x2="21" y2="18"></line>
        </svg>
      </button>
      
      {/* Main sidebar container */}
      <div ref={sidebarRef} className={`chat-history-sidebar ${isOpen ? 'open' : ''}`}>
        {/* Header with title and close button */}
        <SidebarHeader 
          isOpen={isOpen} 
          onClose={closeSidebar} 
        />
        
        {/* New session creation interface */}
        <NewSessionActions 
          onCreateSession={handleCreateWithName}
          isCreating={isCreating}
        />
        
        {/* Session list with active state and interactions */}
        <SessionList
          sessions={sessions}
          currentSessionId={currentSessionId}
          onSwitchSession={handleSwitchSession}
          onDeleteSession={handleDeleteSession}
        />
      </div>
      
      {/* Unified error display component */}
      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </>
  )
}

export default ChatHistorySidebar