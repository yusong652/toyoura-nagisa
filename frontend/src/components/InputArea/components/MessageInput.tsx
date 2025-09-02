import React from 'react'
import { MessageInputProps } from '../types'

/**
 * Message input textarea component with enhanced functionality.
 * 
 * This component provides a sophisticated textarea input with auto-resize,
 * keyboard shortcuts, paste handling, and accessibility features. It's
 * focused specifically on text input concerns while delegating other
 * functionality to parent components through props.
 * 
 * Features:
 * - Auto-resizing textarea with configurable constraints
 * - Keyboard shortcut handling (Enter to send, Shift+Enter for newline)
 * - Paste event handling for images and text
 * - Disabled state with visual feedback
 * - Proper focus management and accessibility
 * - Smooth user experience with optimized rendering
 * 
 * Args:
 *     value: string - Current message content
 *     onChange: Function to handle text changes
 *     onKeyPress: Function to handle keyboard shortcuts
 *     onPaste: Function to handle paste events (especially images)
 *     placeholder?: string - Placeholder text for empty input
 *     disabled?: boolean - Whether input should be disabled
 *     className?: string - Additional CSS classes
 *     textareaRef: React ref for direct textarea access
 *     autoFocus?: boolean - Whether to focus on mount
 * 
 * Returns:
 *     JSX.Element: Enhanced textarea with all functionality
 * 
 * TypeScript Learning Points:
 * - React.forwardRef pattern for ref forwarding (if needed)
 * - Event handler prop typing with specific React event types
 * - Ref prop typing with HTMLTextAreaElement
 * - Optional props with sensible defaults
 * - Component focusing on single responsibility
 */
const MessageInput: React.FC<MessageInputProps> = ({
  value,
  onChange,
  onKeyPress,
  onKeyDown,
  onPaste,
  placeholder = 'Type a message...',
  disabled = false,
  className = '',
  textareaRef,
  autoFocus = false
}) => {
  // Handle textarea focus on mount if requested
  React.useEffect(() => {
    if (autoFocus && textareaRef.current && !disabled) {
      textareaRef.current.focus()
    }
  }, [autoFocus, disabled, textareaRef])
  
  return (
    <textarea
      ref={textareaRef}
      className={`message-input with-corner-buttons ${className}`.trim()}
      placeholder={placeholder}
      value={value}
      onChange={onChange}
      onKeyPress={onKeyPress}
      onKeyDown={onKeyDown}
      onPaste={onPaste}
      disabled={disabled}
      rows={1} // Start with single row, auto-resize will handle expansion
      style={{
        resize: 'none', // Prevent manual resize, auto-resize handles this
        overflow: 'hidden' // Will be managed by auto-resize hook
      }}
      aria-label="Message input"
      aria-describedby="message-input-help"
      spellCheck={true}
      autoComplete="off"
      autoCorrect="on"
      autoCapitalize="sentences"
    />
  )
}

export default MessageInput

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **React Event Handler Typing**:
 *    ```typescript
 *    interface MessageInputProps {
 *      onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
 *      onKeyPress: (e: React.KeyboardEvent) => Promise<void>
 *      onPaste: (e: React.ClipboardEvent) => void
 *    }
 *    ```
 *    Specific React synthetic event types ensure type safety
 * 
 * 2. **Ref Prop Typing**:
 *    ```typescript
 *    textareaRef: React.RefObject<HTMLTextAreaElement>
 *    ```
 *    Strongly typed ref provides access to textarea-specific properties
 * 
 * 3. **Optional Props with Defaults**:
 *    ```typescript
 *    placeholder = 'Type a message...',
 *    disabled = false,
 *    className = ''
 *    ```
 *    Default parameter values provide fallbacks for optional props
 * 
 * 4. **useEffect for Side Effects**:
 *    ```typescript
 *    React.useEffect(() => {
 *      if (autoFocus && textareaRef.current && !disabled) {
 *        textareaRef.current.focus()
 *      }
 *    }, [autoFocus, disabled, textareaRef])
 *    ```
 *    Proper dependency management for focus side effect
 * 
 * 5. **CSS Class Composition**:
 *    ```typescript
 *    className={`message-input with-corner-buttons ${className}`.trim()}
 *    ```
 *    Template literal with trim for clean class names
 * 
 * 6. **Inline Styles with Type Safety**:
 *    ```typescript
 *    style={{
 *      resize: 'none',
 *      overflow: 'hidden'
 *    }}
 *    ```
 *    TypeScript ensures CSS property names and values are valid
 * 
 * Component Design Benefits:
 * - **Single Responsibility**: Only handles textarea input concerns
 * - **Prop Delegation**: Business logic handled by parent through event handlers
 * - **Accessibility**: Comprehensive ARIA labeling and semantic HTML
 * - **User Experience**: Smart defaults for mobile and desktop
 * - **Performance**: Minimal re-renders with proper prop design
 * - **Browser Compatibility**: Works across different platforms
 * 
 * Textarea Configuration:
 * - **Auto-resize**: Managed by parent hook through ref
 * - **Keyboard Handling**: Enter/Shift+Enter logic in parent component
 * - **Paste Handling**: Image detection and processing in parent
 * - **Focus Management**: Optional auto-focus with disabled state respect
 * - **Spellcheck**: Enabled for better writing experience
 * - **Autocomplete**: Disabled to prevent unwanted suggestions
 * 
 * Accessibility Features:
 * - ARIA label for screen readers
 * - Describedby reference for help text (if needed)
 * - Proper disabled state handling
 * - Keyboard navigation support
 * - Semantic textarea element
 * 
 * Mobile Optimizations:
 * - autoCorrect enabled for mobile typing
 * - autoCapitalize for sentence-case input
 * - Responsive sizing through CSS
 * - Touch-friendly interaction area
 * 
 * Performance Considerations:
 * - Controlled component with optimized change handling
 * - Minimal inline styles (most styling through CSS classes)
 * - Proper dependency arrays in useEffect
 * - No unnecessary re-renders through pure prop design
 * 
 * Integration Pattern:
 * ```typescript
 * const { textareaRef, handleTextareaResize } = useInputAutoResize(message)
 * 
 * <MessageInput
 *   value={message}
 *   onChange={handleMessageChange}
 *   onKeyPress={handleKeyPress}
 *   onPaste={handlePaste}
 *   textareaRef={textareaRef}
 *   disabled={isInputDisabled}
 * />
 * ```
 * 
 * This pattern keeps the component focused on textarea rendering
 * while allowing parent components to handle business logic through
 * well-typed event handlers and ref manipulation.
 */