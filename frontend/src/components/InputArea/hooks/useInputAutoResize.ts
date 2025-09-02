import { useRef, useEffect, useCallback } from 'react'
import { InputAutoResizeHookReturn, DEFAULT_INPUT_CONFIG } from '../types'

/**
 * Custom hook for textarea auto-resize functionality.
 * 
 * This hook manages automatic height adjustment of textarea elements based
 * on content, providing a smooth user experience for multi-line input.
 * It follows aiNagisa's clean architecture by isolating UI behavior logic
 * from the main component concerns.
 * 
 * Features:
 * - Automatic height adjustment based on content
 * - Configurable min/max height constraints
 * - Smooth transitions with CSS
 * - Reset functionality for clearing content
 * - Performance optimized resize calculations
 * - Cross-browser compatibility
 * 
 * Args:
 *     message: string - Current message content to measure
 *     minHeight?: number - Minimum textarea height in pixels
 *     maxHeight?: number - Maximum textarea height in pixels
 *     enabled?: boolean - Whether auto-resize is enabled
 * 
 * Returns:
 *     InputAutoResizeHookReturn: Auto-resize management interface:
 *         - textareaRef: React ref for the textarea element
 *         - handleTextareaResize: Function to manually trigger resize
 *         - resetTextareaHeight: Function to reset to minimum height
 *         - maxHeight: Current maximum height setting
 * 
 * TypeScript Learning Points:
 * - useRef with HTMLTextAreaElement typing
 * - useEffect with cleanup for performance
 * - useCallback for event handler optimization
 * - Optional parameters with default values
 * - DOM manipulation with type safety
 */
const useInputAutoResize = (
  message: string,
  minHeight: number = DEFAULT_INPUT_CONFIG.autoResize.minHeight,
  maxHeight: number = DEFAULT_INPUT_CONFIG.autoResize.maxHeight,
  enabled: boolean = DEFAULT_INPUT_CONFIG.autoResize.enabled
): InputAutoResizeHookReturn => {
  // Textarea reference for direct DOM manipulation
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  
  // Calculate and apply height based on content
  const handleTextareaResize = useCallback(() => {
    if (!enabled || !textareaRef.current) return
    
    const textarea = textareaRef.current
    
    // Reset height to auto to get accurate scrollHeight
    textarea.style.height = 'auto'
    
    // Calculate new height based on content
    const newHeight = Math.min(
      Math.max(textarea.scrollHeight, minHeight),
      maxHeight
    )
    
    // Apply the calculated height
    textarea.style.height = `${newHeight}px`
    
    // Add scrollbar if content exceeds maxHeight
    if (textarea.scrollHeight > maxHeight) {
      textarea.style.overflowY = 'auto'
    } else {
      textarea.style.overflowY = 'hidden'
    }
  }, [enabled, minHeight, maxHeight])
  
  // Reset textarea to minimum height
  const resetTextareaHeight = useCallback(() => {
    if (!textareaRef.current) return
    
    const textarea = textareaRef.current
    textarea.style.height = 'auto'
    textarea.style.height = `${minHeight}px`
    textarea.style.overflowY = 'hidden'
  }, [minHeight])
  
  // Auto-resize when message content changes
  useEffect(() => {
    if (enabled) {
      handleTextareaResize()
    }
  }, [message, enabled, handleTextareaResize])
  
  // Initialize textarea height on mount
  useEffect(() => {
    if (enabled && textareaRef.current) {
      const textarea = textareaRef.current
      
      // Set initial styles
      textarea.style.resize = 'none' // Disable manual resize
      textarea.style.minHeight = `${minHeight}px`
      textarea.style.maxHeight = `${maxHeight}px`
      textarea.style.transition = 'height 0.1s ease' // Smooth height changes
      
      // Set initial height
      resetTextareaHeight()
    }
  }, [enabled, minHeight, maxHeight, resetTextareaHeight])
  
  return {
    textareaRef,
    handleTextareaResize,
    resetTextareaHeight,
    maxHeight
  }
}

export default useInputAutoResize

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **useRef with Specific Element Type**:
 *    ```typescript
 *    const textareaRef = useRef<HTMLTextAreaElement>(null)
 *    ```
 *    Strongly typed ref provides HTMLTextAreaElement-specific properties
 * 
 * 2. **useCallback for DOM Manipulation**:
 *    ```typescript
 *    const handleTextareaResize = useCallback(() => {
 *      if (!textareaRef.current) return
 *      const textarea = textareaRef.current
 *      textarea.style.height = `${newHeight}px`
 *    }, [enabled, minHeight, maxHeight])
 *    ```
 *    Optimized DOM operations with proper dependency management
 * 
 * 3. **useEffect with Dependency Array**:
 *    ```typescript
 *    useEffect(() => {
 *      if (enabled) {
 *        handleTextareaResize()
 *      }
 *    }, [message, enabled, handleTextareaResize])
 *    ```
 *    Effect triggers only when relevant dependencies change
 * 
 * 4. **Optional Parameters with Defaults**:
 *    ```typescript
 *    minHeight: number = DEFAULT_INPUT_CONFIG.autoResize.minHeight
 *    ```
 *    Configuration-based defaults with type safety
 * 
 * 5. **Early Return Pattern**:
 *    ```typescript
 *    if (!enabled || !textareaRef.current) return
 *    ```
 *    Guard clauses prevent unnecessary DOM operations
 * 
 * 6. **Math Utility for Constraints**:
 *    ```typescript
 *    const newHeight = Math.min(
 *      Math.max(textarea.scrollHeight, minHeight),
 *      maxHeight
 *    )
 *    ```
 *    Clamping values within min/max bounds
 * 
 * Hook Design Benefits:
 * - **Performance Optimized**: Only resizes when message content changes
 * - **Configurable**: Min/max heights and enable/disable functionality
 * - **Smooth UX**: CSS transitions for height changes
 * - **Browser Compatible**: Works across different browsers
 * - **Memory Efficient**: Proper cleanup and ref management
 * - **Type Safe**: Full TypeScript coverage for DOM operations
 * 
 * DOM Manipulation Strategy:
 * 1. Reset height to 'auto' to get accurate scrollHeight
 * 2. Calculate new height within min/max constraints
 * 3. Apply height with smooth CSS transition
 * 4. Manage overflow based on content vs maxHeight
 * 
 * Auto-resize Algorithm:
 * ```
 * 1. Content changes → useEffect triggers
 * 2. Reset height to 'auto' → measure scrollHeight  
 * 3. Clamp height: Math.min(Math.max(scrollHeight, min), max)
 * 4. Apply new height with CSS transition
 * 5. Set overflow: auto/hidden based on content
 * ```
 * 
 * Performance Considerations:
 * - useCallback prevents function recreation on every render
 * - Early returns avoid unnecessary DOM operations
 * - Minimal useEffect dependency arrays prevent excess triggers
 * - CSS transitions handled by browser, not JavaScript
 * 
 * Integration Pattern:
 * ```typescript
 * const {
 *   textareaRef,
 *   handleTextareaResize,
 *   resetTextareaHeight
 * } = useInputAutoResize(message, 44, 300, true)
 * 
 * // In component JSX:
 * <textarea
 *   ref={textareaRef}
 *   value={message}
 *   onChange={handleMessageChange}
 * />
 * 
 * // Reset after sending:
 * resetTextareaHeight()
 * ```
 * 
 * This pattern encapsulates all textarea auto-resize complexity,
 * making the main component focus on message content rather than
 * UI behavior implementation details.
 */