/**
 * Custom hook for managing sidebar open/closed state.
 * 
 * This hook encapsulates the sidebar visibility logic, including
 * body class management for layout adjustments when sidebar is open.
 */

import { useState, useCallback } from 'react'
import { SidebarStateReturn } from '../types'

/**
 * Hook to manage sidebar open/closed state with body class synchronization.
 * 
 * @returns SidebarStateReturn object containing:
 *   - isOpen: boolean - Current sidebar visibility state
 *   - toggleSidebar: () => void - Toggle sidebar open/closed
 *   - closeSidebar: () => void - Force close the sidebar
 * 
 * @example
 * const { isOpen, toggleSidebar, closeSidebar } = useSidebarState()
 * 
 * Note:
 * This hook manages the 'sidebar-open' class on document.body
 * to enable CSS-based layout adjustments when sidebar is visible.
 */
export const useSidebarState = (): SidebarStateReturn => {
  // State: Track sidebar visibility
  const [isOpen, setIsOpen] = useState<boolean>(false)
  
  /**
   * Toggle sidebar visibility and update body class.
   * Uses callback to ensure state consistency.
   */
  const toggleSidebar = useCallback(() => {
    setIsOpen(prev => {
      const newState = !prev
      // Sync body class with sidebar state for CSS-based layout adjustments
      if (newState) {
        document.body.classList.add('sidebar-open')
      } else {
        document.body.classList.remove('sidebar-open')
      }
      return newState
    })
  }, [])
  
  /**
   * Force close the sidebar and remove body class.
   * Typically used after user actions like selecting a session.
   */
  const closeSidebar = useCallback(() => {
    setIsOpen(false)
    document.body.classList.remove('sidebar-open')
  }, [])
  
  return {
    isOpen,
    toggleSidebar,
    closeSidebar
  }
}