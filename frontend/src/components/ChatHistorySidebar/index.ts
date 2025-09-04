/**
 * ChatHistorySidebar module exports.
 * 
 * This index file provides clean exports for the ChatHistorySidebar
 * component, following the modular architecture pattern.
 */

// Main component export
export { default } from './ChatHistorySidebar'

// Type exports for external use
export type {
  ChatHistorySidebarProps,
  SidebarHeaderProps,
  NewSessionActionsProps,
  SessionListProps,
  SessionItemProps,
  SidebarStateReturn,
  SessionManagementReturn,
  DateFormatter
} from './types'

// Hook exports for reusability
export { useSidebarState } from './hooks/useSidebarState'
export { useSessionManagement } from './hooks/useSessionManagement'

// Sub-component exports (if needed externally)
export { default as SidebarHeader } from './header/SidebarHeader'
export { default as NewSessionActions } from './actions/NewSessionActions'
export { default as SessionList } from './list/SessionList'
export { default as SessionItem } from './list/SessionItem'