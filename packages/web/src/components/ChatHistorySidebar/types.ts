/**
 * Type definitions for ChatHistorySidebar component.
 * 
 * This module defines all TypeScript interfaces and types used throughout
 * the ChatHistorySidebar component hierarchy, ensuring type safety and
 * clear component contracts.
 */

import { ChatSession } from '@aiNagisa/core'

/**
 * Props for the main ChatHistorySidebar component.
 * Currently empty but prepared for future extensibility.
 */
export interface ChatHistorySidebarProps {}

/**
 * Props for the sidebar header component.
 * 
 * @property isOpen - Whether the sidebar is currently open
 * @property onClose - Callback to close the sidebar
 */
export interface SidebarHeaderProps {
  isOpen: boolean
  onClose: () => void
}

/**
 * Props for the new session creation component.
 * 
 * @property onCreateSession - Async callback to create a new session
 * @property isCreating - Whether a session is currently being created
 */
export interface NewSessionActionsProps {
  onCreateSession: (name: string) => Promise<void>
  isCreating: boolean
}

/**
 * Props for the session list component.
 * 
 * @property sessions - Array of chat sessions to display
 * @property currentSessionId - ID of the currently active session
 * @property onSwitchSession - Callback to switch to a different session
 * @property onDeleteSession - Async callback to delete a session
 */
export interface SessionListProps {
  sessions: ChatSession[]
  currentSessionId: string | null
  onSwitchSession: (sessionId: string) => void
  onDeleteSession: (e: React.MouseEvent, sessionId: string) => Promise<void>
}

/**
 * Props for individual session item component.
 * 
 * @property session - The chat session data
 * @property isActive - Whether this session is currently active
 * @property onSelect - Callback when session is selected
 * @property onDelete - Async callback to delete this session
 */
export interface SessionItemProps {
  session: ChatSession
  isActive: boolean
  onSelect: () => void
  onDelete: (e: React.MouseEvent) => Promise<void>
}

/**
 * Return type for the useSidebarState hook.
 * 
 * @property isOpen - Whether the sidebar is currently open
 * @property toggleSidebar - Function to toggle sidebar open/closed state
 * @property closeSidebar - Function to close the sidebar
 */
export interface SidebarStateReturn {
  isOpen: boolean
  toggleSidebar: () => void
  closeSidebar: () => void
}

/**
 * Return type for the useSessionManagement hook.
 * 
 * @property newSessionName - Current value of new session name input
 * @property setNewSessionName - Function to update new session name
 * @property isCreating - Whether a session is currently being created
 * @property handleCreateSession - Async function to create a new session
 * @property handleSwitchSession - Function to switch to a different session
 * @property handleDeleteSession - Async function to delete a session
 */
export interface SessionManagementReturn {
  newSessionName: string
  setNewSessionName: (name: string) => void
  isCreating: boolean
  handleCreateSession: () => Promise<void>
  handleSwitchSession: (sessionId: string) => void
  handleDeleteSession: (e: React.MouseEvent, sessionId: string) => Promise<void>
}

/**
 * Date formatting utility type.
 * Represents functions that format date strings for display.
 */
export type DateFormatter = (date: string) => string