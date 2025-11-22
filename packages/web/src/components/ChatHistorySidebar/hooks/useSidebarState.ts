/**
 * Custom hook for managing sidebar open/closed state.
 * 
 * This hook encapsulates the sidebar visibility logic, including
 * body class management for layout adjustments when sidebar is open,
 * and click outside to close functionality.
 */

import { useState, useCallback, useEffect, useRef } from 'react'
import { SidebarStateReturn } from '../types'

/**
 * Hook to manage sidebar open/closed state with body class synchronization
 * and click outside to close functionality.
 * 
 * @returns SidebarStateReturn object containing:
 *   - isOpen: boolean - Current sidebar visibility state
 *   - toggleSidebar: () => void - Toggle sidebar open/closed
 *   - closeSidebar: () => void - Force close the sidebar
 *   - sidebarRef: RefObject - Ref to attach to sidebar element
 *   - toggleRef: RefObject - Ref to attach to toggle button
 * 
 * @example
 * const { isOpen, toggleSidebar, closeSidebar, sidebarRef, toggleRef } = useSidebarState()
 * 
 * Note:
 * This hook manages the 'sidebar-open' class on document.body
 * to enable CSS-based layout adjustments when sidebar is visible.
 * It also handles clicking outside the sidebar to close it.
 */
export const useSidebarState = (): SidebarStateReturn & { 
  sidebarRef: React.RefObject<HTMLDivElement | null>
  toggleRef: React.RefObject<HTMLButtonElement | null>
} => {
  // State: Track sidebar visibility
  const [isOpen, setIsOpen] = useState<boolean>(false)
  
  // Refs for click outside detection
  const sidebarRef = useRef<HTMLDivElement>(null)
  const toggleRef = useRef<HTMLButtonElement>(null)
  
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
  
  /**
   * Handle click outside to close sidebar
   */
  useEffect(() => {
    if (!isOpen) return
    
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node
      
      // Don't close if clicking on sidebar or toggle button
      if (
        sidebarRef.current?.contains(target) ||
        toggleRef.current?.contains(target)
      ) {
        return
      }
      
      // Close sidebar when clicking outside
      closeSidebar()
    }
    
    // Add event listener with a small delay to avoid immediate closure
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside)
    }, 100)
    
    return () => {
      clearTimeout(timeoutId)
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen, closeSidebar])
  
  return {
    isOpen,
    toggleSidebar,
    closeSidebar,
    sidebarRef,
    toggleRef
  }
}