import { useCallback, useState, useEffect } from 'react'
import { UseMediaModalReturn, CloseReason } from '../types'

/**
 * Custom hook for managing media modal behavior.
 * 
 * Handles common modal interactions including background clicks,
 * escape key handling, and animation states. Provides standardized
 * behavior across all media modal types (Image, Video, etc.).
 * 
 * Args:
 *     open: Whether the modal is currently open
 *     onClose: Callback function to close the modal
 *     preventBackgroundClose: Disable closing on background click
 *     preventEscapeClose: Disable closing on escape key
 * 
 * Returns:
 *     UseMediaModalReturn: Object containing:
 *         - handleBackgroundClick: Handler for overlay clicks
 *         - handleContainerClick: Handler to stop event propagation
 *         - isClosing: Animation state for smooth transitions
 * 
 * TypeScript Learning Points:
 * - Event handler typing with React.MouseEvent
 * - Optional parameters with default values
 * - useCallback for performance optimization
 * - Cleanup functions in useEffect
 */
export const useMediaModal = (
  open: boolean,
  onClose: () => void,
  preventBackgroundClose: boolean = false,
  preventEscapeClose: boolean = false
): UseMediaModalReturn => {
  const [isClosing, setIsClosing] = useState(false)
  
  /**
   * Handle clicks on the background overlay.
   * Only closes if clicking directly on the overlay, not its children.
   */
  const handleBackgroundClick = useCallback((e: React.MouseEvent) => {
    if (!preventBackgroundClose && e.target === e.currentTarget) {
      onClose()
    }
  }, [preventBackgroundClose, onClose])
  
  /**
   * Handle clicks on the container to prevent propagation.
   * Prevents the modal from closing when clicking on content.
   */
  const handleContainerClick = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
  }, [])
  
  /**
   * Handle escape key press for closing the modal.
   * Can be disabled via preventEscapeClose prop.
   */
  useEffect(() => {
    if (!open || preventEscapeClose) return
    
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [open, onClose, preventEscapeClose])
  
  /**
   * Handle closing animation state.
   * Provides a delay for exit animations.
   */
  useEffect(() => {
    if (!open && !isClosing) {
      setIsClosing(true)
      const timer = setTimeout(() => setIsClosing(false), 200)
      return () => clearTimeout(timer)
    }
  }, [open, isClosing])
  
  return {
    handleBackgroundClick,
    handleContainerClick,
    isClosing
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Custom Hook Return Types:
 *    Explicitly typed return object for contract clarity
 * 
 * 2. Event Handler Typing:
 *    React.MouseEvent for type-safe event handling
 * 
 * 3. Optional Parameters:
 *    Default values provide flexible API
 * 
 * 4. useCallback Dependencies:
 *    Proper dependency arrays prevent stale closures
 * 
 * 5. Effect Cleanup:
 *    Return functions remove event listeners properly
 * 
 * Benefits of This Hook:
 * - Centralizes common modal behavior
 * - Prevents code duplication across modal types
 * - Provides consistent UX patterns
 * - Memory leak prevention with proper cleanup
 * - Performance optimized with memoization
 */