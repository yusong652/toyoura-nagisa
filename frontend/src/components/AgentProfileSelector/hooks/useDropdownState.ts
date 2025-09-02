import { useState, useRef, useEffect } from 'react'
import { DropdownStateHookReturn } from '../types'

/**
 * Custom hook for managing dropdown state and click-outside behavior.
 * 
 * Handles dropdown open/close state, ref management for click-outside detection,
 * and automatic cleanup of event listeners. Follows aiNagisa's hook patterns
 * with proper TypeScript typing and resource management.
 * 
 * Returns:
 *     DropdownStateHookReturn: Complete dropdown state management:
 *         - isOpen: boolean - Current dropdown open state
 *         - setIsOpen: (open: boolean) => void - State setter function
 *         - dropdownRef: React.RefObject<HTMLDivElement> - Ref for click-outside detection
 * 
 * TypeScript Learning Points:
 * - useRef with generic typing for specific DOM elements
 * - useEffect cleanup patterns for event listeners
 * - Node type checking for click-outside detection
 * - Proper dependency arrays for effect optimization
 */
export const useDropdownState = (): DropdownStateHookReturn => {
  const [isOpen, setIsOpen] = useState<boolean>(false)
  const dropdownRef = useRef<HTMLDivElement>(null)
  
  // Handle click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent): void => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    // Only add listener when dropdown is open
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])
  
  return {
    isOpen,
    setIsOpen,
    dropdownRef
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Generic Ref Typing:
 *    useRef<HTMLDivElement> provides type-safe DOM element access
 * 
 * 2. Event Listener Cleanup:
 *    useEffect return function removes listeners properly
 * 
 * 3. Type Assertion:
 *    event.target as Node for DOM type compatibility
 * 
 * 4. Conditional Effect Logic:
 *    Only attach listeners when dropdown is open for performance
 * 
 * 5. Clean Interface Design:
 *    Returns exactly what the component needs, nothing more
 * 
 * Benefits of This Pattern:
 * - Automatic click-outside handling
 * - Memory leak prevention with proper cleanup
 * - Performance optimization (listeners only when needed)
 * - Reusable across dropdown components
 * - Type-safe DOM interactions
 */