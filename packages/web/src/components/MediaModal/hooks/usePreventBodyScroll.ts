import { useEffect, useRef } from 'react'
import { UsePreventBodyScrollOptions } from '../types'

/**
 * Custom hook to prevent body scrolling when modal is open.
 * 
 * Manages document.body overflow style to prevent background scrolling
 * while preserving the original scroll position. Handles cleanup
 * automatically on unmount or when disabled.
 * 
 * Args:
 *     options: Configuration object:
 *         - enabled: Whether to prevent scrolling
 *         - restoreOnUnmount: Whether to restore original overflow on unmount
 * 
 * TypeScript Learning Points:
 * - useRef for storing non-reactive values
 * - Optional object destructuring with defaults
 * - Cleanup patterns with useEffect
 * - Type-safe options pattern
 */
export const usePreventBodyScroll = ({
  enabled,
  restoreOnUnmount = true
}: UsePreventBodyScrollOptions): void => {
  const originalOverflowRef = useRef<string>('')
  const scrollPositionRef = useRef<number>(0)
  
  useEffect(() => {
    if (!enabled) return
    
    // Store original values
    originalOverflowRef.current = document.body.style.overflow
    scrollPositionRef.current = window.scrollY
    
    // Prevent scrolling
    document.body.style.overflow = 'hidden'
    
    // Cleanup function
    return () => {
      if (restoreOnUnmount) {
        document.body.style.overflow = originalOverflowRef.current
        // Restore scroll position if needed
        if (scrollPositionRef.current > 0) {
          window.scrollTo(0, scrollPositionRef.current)
        }
      }
    }
  }, [enabled, restoreOnUnmount])
  
  // Handle changes to enabled state
  useEffect(() => {
    if (!enabled && originalOverflowRef.current) {
      document.body.style.overflow = originalOverflowRef.current
    }
  }, [enabled])
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Void Return Type:
 *    Hook has side effects only, no return value
 * 
 * 2. useRef with Type Parameter:
 *    Stores non-reactive values with type safety
 * 
 * 3. Object Destructuring:
 *    Clean parameter extraction with defaults
 * 
 * 4. Conditional Cleanup:
 *    Return cleanup function only when needed
 * 
 * 5. Multiple Effects:
 *    Separate concerns for different behaviors
 * 
 * Benefits of This Hook:
 * - Prevents scroll-related UX issues
 * - Preserves scroll position across modal sessions
 * - Automatic cleanup prevents memory leaks
 * - Configurable restoration behavior
 * - Zero dependencies for maximum reusability
 */