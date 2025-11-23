import { useCallback } from 'react'
import { useAgent } from '../../../contexts/agent/AgentContext'
import { AgentProfileType } from '@aiNagisa/core'
import { useErrorDisplay } from '../../../hooks/useErrorDisplay'
import { ProfileSelectorEventHandlers, ProfileChangeHandler } from '../types'

/**
 * Custom hook for managing AgentProfileSelector event handlers.
 * 
 * Provides all event handling logic for profile selection, dropdown interaction,
 * and keyboard navigation. Follows aiNagisa's event handling patterns with
 * proper error handling and context integration.
 * 
 * Args:
 *     useContext: Whether to use AgentContext for profile changes
 *     propOnProfileChange: Profile change handler passed via props
 *     currentProfile: Currently selected profile
 *     isLoading: Loading state to prevent interactions
 *     isOpen: Dropdown open state
 *     setIsOpen: Function to control dropdown state
 * 
 * Returns:
 *     ProfileSelectorEventHandlers: Complete event handler object:
 *         - handleProfileSelect: (profile: AgentProfileType) => Promise<void>
 *         - handleToggleDropdown: () => void
 *         - handleKeyDown: (event: React.KeyboardEvent) => void
 *         - handleClickOutside: (event: MouseEvent) => void
 * 
 * TypeScript Learning Points:
 * - useCallback for performance optimization of event handlers
 * - Promise-returning async handlers with proper error handling
 * - Event parameter typing for keyboard and mouse events
 * - Conditional logic with type guards
 */
export const useProfileSelectorEvents = (
  useContext: boolean,
  propOnProfileChange?: ProfileChangeHandler,
  currentProfile?: AgentProfileType,
  isLoading: boolean = false,
  isOpen: boolean = false,
  setIsOpen?: (open: boolean) => void
): ProfileSelectorEventHandlers => {
  // Context integration when needed
  const contextAgent = useAgent()
  const { showTemporaryError } = useErrorDisplay()
  
  /**
   * Handle profile selection with error handling and context support.
   * Prevents duplicate selections and manages loading states.
   */
  const handleProfileSelect = useCallback(async (profile: AgentProfileType): Promise<void> => {
    // Prevent interaction during loading or duplicate selection
    if (profile === currentProfile || isLoading) {
      setIsOpen?.(false)
      return
    }
    
    try {
      if (useContext) {
        // Use context for profile change (now synchronous)
        contextAgent.setCurrentProfile(profile)
        // Close dropdown after successful change
        setIsOpen?.(false)
      } else if (propOnProfileChange) {
        // Use provided handler for profile change
        await propOnProfileChange(profile)
        // Close dropdown after successful change
        setIsOpen?.(false)
      } else {
        console.warn('No profile change handler available')
        setIsOpen?.(false)
      }
    } catch (error) {
      console.error('Failed to change agent profile:', error)
      
      // Show error message (for props-based handlers that might throw)
      const errorMessage = error instanceof Error 
        ? error.message 
        : 'Failed to change agent profile. Please try again.'
      showTemporaryError(errorMessage, 4000)
      
      // Keep dropdown open on error for retry
    }
  }, [
    currentProfile, 
    isLoading, 
    useContext, 
    contextAgent, 
    propOnProfileChange, 
    setIsOpen, 
    showTemporaryError
  ])
  
  /**
   * Toggle dropdown visibility with loading state check.
   */
  const handleToggleDropdown = useCallback((): void => {
    if (!isLoading && setIsOpen) {
      setIsOpen(!isOpen)
    }
  }, [isLoading, isOpen, setIsOpen])
  
  /**
   * Handle keyboard navigation for accessibility.
   * Supports Escape (close), Enter/Space (toggle).
   */
  const handleKeyDown = useCallback((event: React.KeyboardEvent): void => {
    if (event.key === 'Escape') {
      setIsOpen?.(false)
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      if (!isLoading && setIsOpen) {
        setIsOpen(!isOpen)
      }
    }
  }, [isLoading, isOpen, setIsOpen])
  
  /**
   * Handle clicks outside the component to close dropdown.
   * Used with useEffect for proper cleanup.
   */
  const handleClickOutside = useCallback((event: MouseEvent): void => {
    // This handler will be used in useEffect with dropdownRef
    // The actual implementation is in useDropdownState hook
    setIsOpen?.(false)
  }, [setIsOpen])
  
  return {
    handleProfileSelect,
    handleToggleDropdown,
    handleKeyDown,
    handleClickOutside
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. useCallback Performance Optimization:
 *    Prevents unnecessary re-renders by memoizing event handlers
 * 
 * 2. Async Event Handlers:
 *    Promise-returning functions with proper error handling
 * 
 * 3. Event Parameter Typing:
 *    React.KeyboardEvent and MouseEvent for type-safe event handling
 * 
 * 4. Conditional Logic with Type Safety:
 *    Optional chaining and type guards prevent runtime errors
 * 
 * 5. Dependency Arrays:
 *    Explicit dependencies ensure callbacks update when needed
 * 
 * Benefits of This Architecture:
 * - Centralized event handling logic
 * - Consistent error handling patterns
 * - Accessibility features built-in
 * - Performance-optimized with memoization
 * - Easy to test event handlers in isolation
 * - Supports both context and props-based usage
 */