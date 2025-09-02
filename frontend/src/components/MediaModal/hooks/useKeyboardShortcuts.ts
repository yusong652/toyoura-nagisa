import { useEffect, useCallback, useRef } from 'react'
import { UseKeyboardShortcutsOptions, KEYBOARD_SHORTCUTS } from '../types'

/**
 * Custom hook for managing keyboard shortcuts in media modals.
 * 
 * Provides standardized keyboard interaction patterns for media viewers
 * with support for navigation, zoom controls, and custom shortcuts.
 * Prevents event conflicts and handles cleanup automatically.
 * 
 * Args:
 *     options: Configuration object:
 *         - onClose: Handler for escape key
 *         - onNext: Handler for right arrow
 *         - onPrevious: Handler for left arrow
 *         - onZoomIn: Handler for plus key
 *         - onZoomOut: Handler for minus key
 *         - onZoomReset: Handler for zero key
 *         - customHandlers: Additional key handlers
 *         - disabled: Disable all shortcuts
 * 
 * TypeScript Learning Points:
 * - Complex options object with optional callbacks
 * - Record type for dynamic key-value pairs
 * - useRef for stable handler references
 * - Event.preventDefault() for browser defaults
 */
export const useKeyboardShortcuts = ({
  onClose,
  onNext,
  onPrevious,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  customHandlers = {},
  disabled = false
}: UseKeyboardShortcutsOptions = {}): void => {
  // Use ref to avoid recreating handler on every render
  const handlersRef = useRef<UseKeyboardShortcutsOptions>({})
  
  // Update handlers ref when they change
  useEffect(() => {
    handlersRef.current = {
      onClose,
      onNext,
      onPrevious,
      onZoomIn,
      onZoomOut,
      onZoomReset,
      customHandlers
    }
  }, [onClose, onNext, onPrevious, onZoomIn, onZoomOut, onZoomReset, customHandlers])
  
  /**
   * Main keyboard event handler.
   * Maps keys to their respective handlers with conflict prevention.
   */
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (disabled) return
    
    const handlers = handlersRef.current
    
    // Check custom handlers first (higher priority)
    if (handlers.customHandlers && handlers.customHandlers[e.key]) {
      handlers.customHandlers[e.key](e)
      return
    }
    
    // Standard shortcuts
    switch (e.key) {
      case KEYBOARD_SHORTCUTS.CLOSE:
        if (handlers.onClose) {
          e.preventDefault()
          handlers.onClose()
        }
        break
        
      case KEYBOARD_SHORTCUTS.NEXT:
        if (handlers.onNext) {
          e.preventDefault()
          handlers.onNext()
        }
        break
        
      case KEYBOARD_SHORTCUTS.PREVIOUS:
        if (handlers.onPrevious) {
          e.preventDefault()
          handlers.onPrevious()
        }
        break
        
      case KEYBOARD_SHORTCUTS.ZOOM_IN:
      case '=': // Alternative for zoom in
        if (handlers.onZoomIn) {
          e.preventDefault()
          handlers.onZoomIn()
        }
        break
        
      case KEYBOARD_SHORTCUTS.ZOOM_OUT:
      case '_': // Alternative for zoom out
        if (handlers.onZoomOut) {
          e.preventDefault()
          handlers.onZoomOut()
        }
        break
        
      case KEYBOARD_SHORTCUTS.ZOOM_RESET:
        if (handlers.onZoomReset) {
          e.preventDefault()
          handlers.onZoomReset()
        }
        break
        
      default:
        // No action for other keys
        break
    }
  }, [disabled])
  
  /**
   * Attach and cleanup keyboard event listeners.
   * Uses capture phase to handle events before other listeners.
   */
  useEffect(() => {
    if (disabled) return
    
    // Use capture phase for higher priority
    document.addEventListener('keydown', handleKeyDown, true)
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown, true)
    }
  }, [handleKeyDown, disabled])
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Optional Callback Pattern:
 *    All handlers are optional for flexible usage
 * 
 * 2. Record Type:
 *    customHandlers: Record<string, (e: KeyboardEvent) => void>
 *    Allows dynamic key-handler mapping
 * 
 * 3. useRef for Stability:
 *    Prevents handler recreation on every render
 * 
 * 4. Switch Statement with Constants:
 *    Type-safe key mapping using const object
 * 
 * 5. Event Capture:
 *    addEventListener with true for capture phase
 * 
 * Benefits of This Hook:
 * - Standardized keyboard interactions across modals
 * - Prevents browser default behaviors
 * - Custom shortcuts support for extensibility
 * - Performance optimized with refs and callbacks
 * - Clean separation of concerns
 * - Automatic cleanup on unmount
 * 
 * Usage Example:
 * ```typescript
 * useKeyboardShortcuts({
 *   onClose: () => setModalOpen(false),
 *   onNext: () => navigateToNext(),
 *   customHandlers: {
 *     'f': () => toggleFullscreen(),
 *     ' ': () => togglePlayPause()
 *   }
 * })
 * ```
 */