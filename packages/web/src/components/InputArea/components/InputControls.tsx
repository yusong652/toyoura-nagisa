import React from 'react'
import { InputControlsProps } from '../types'
import { CollapsibleToolbar } from '../../CollapsibleToolbar'

/**
 * Input controls component for action buttons and toolbar.
 * 
 * This component provides all the action buttons and controls around the
 * message input, including file upload, toolbar, and send functionality.
 * It focuses on UI controls while delegating business logic to parent
 * components through props.
 * 
 * Features:
 * - File upload button with icon
 * - CollapsibleToolbar integration for agent settings
 * - Send button with loading states
 * - Proper disabled states and visual feedback
 * - Accessible button markup with ARIA labels
 * - Responsive layout for different screen sizes
 * 
 * Args:
 *     onSendMessage: Function to handle message sending
 *     onFileSelect: Function to open file selector
 *     canSendMessage: boolean indicating if message can be sent
 *     isSending: boolean indicating if send is in progress
 *     className?: string - Optional CSS classes
 *     showFileButton?: boolean - Whether to show file upload button
 *     showToolbar?: boolean - Whether to show collapsible toolbar
 * 
 * Returns:
 *     JSX.Element: Complete input controls with buttons and toolbar
 * 
 * TypeScript Learning Points:
 * - Component composition with external components
 * - Boolean props for conditional rendering
 * - Event handler props with async support
 * - SVG icon embedding with proper accessibility
 * - CSS class composition with conditionals
 */
const InputControls: React.FC<InputControlsProps> = ({
  onSendMessage,
  onFileSelect,
  canSendMessage,
  isSending,
  className = '',
  showFileButton = true,
  showToolbar = true
}) => {
  // Handle send button click
  const handleSendClick = async () => {
    if (canSendMessage && !isSending) {
      await onSendMessage()
    }
  }
  
  // Handle file button click
  const handleFileClick = () => {
    if (!isSending) {
      onFileSelect()
    }
  }
  
  return (
    <>
      {/* Corner buttons positioned above textarea */}
      <div className={`input-corner-buttons ${className}`.trim()}>
        {showFileButton && (
          <button 
            className="add-file-btn" 
            onClick={handleFileClick}
            disabled={isSending}
            title="Add Files"
            type="button"
            aria-label="Upload files"
          >
            <svg 
              viewBox="0 0 24 24" 
              width="18" 
              height="18" 
              stroke="currentColor" 
              strokeWidth="2" 
              fill="none"
              aria-hidden="true"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        )}
        
        {showToolbar && <CollapsibleToolbar />}
        
        {/* Hidden file input for file selection */}
        <input
          type="file"
          className="file-input"
          onChange={() => {}} // Handled by parent through onFileSelect
          multiple
          hidden
          aria-hidden="true"
        />
      </div>
      
      {/* Send button positioned beside textarea */}
      <button 
        className={`send-button ${isSending ? 'sending' : ''} ${canSendMessage ? 'enabled' : 'disabled'}`.trim()}
        onClick={handleSendClick}
        disabled={!canSendMessage || isSending}
        title={isSending ? 'Sending...' : 'Send Message'}
        type="button"
        aria-label={isSending ? 'Sending message' : 'Send message'}
      >
        {isSending ? (
          // Loading spinner SVG
          <svg 
            viewBox="0 0 24 24" 
            width="28" 
            height="28" 
            fill="none"
            className="loading-spinner"
            aria-hidden="true"
          >
            <circle 
              cx="12" 
              cy="12" 
              r="10" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeDasharray="60"
              strokeDashoffset="20"
              opacity="0.3"
            />
            <circle 
              cx="12" 
              cy="12" 
              r="10" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeDasharray="15"
              strokeDashoffset="0"
              transform="rotate(90 12 12)"
            />
          </svg>
        ) : (
          // Send icon SVG
          <svg 
            viewBox="0 0 24 24" 
            width="28" 
            height="28" 
            stroke="currentColor" 
            strokeWidth="2" 
            fill="none"
            aria-hidden="true"
          >
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        )}
      </button>
    </>
  )
}

export default InputControls

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Async Event Handler Props**:
 *    ```typescript
 *    interface InputControlsProps {
 *      onSendMessage: () => Promise<void>
 *      onFileSelect: () => void
 *    }
 *    ```
 *    Distinguishes between sync and async event handlers
 * 
 * 2. **Boolean Props for UI State**:
 *    ```typescript
 *    canSendMessage: boolean
 *    isSending: boolean
 *    showFileButton?: boolean
 *    ```
 *    Boolean props control component behavior and appearance
 * 
 * 3. **Conditional CSS Classes**:
 *    ```typescript
 *    className={`send-button ${isSending ? 'sending' : ''} ${canSendMessage ? 'enabled' : 'disabled'}`.trim()}
 *    ```
 *    Dynamic class composition based on component state
 * 
 * 4. **Conditional Rendering with Fragments**:
 *    ```typescript
 *    {showFileButton && (
 *      <button className="add-file-btn" />
 *    )}
 *    ```
 *    React fragments and conditional rendering for flexible UI
 * 
 * 5. **SVG Icon Integration**:
 *    ```typescript
 *    <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
 *      <line x1="12" y1="5" x2="12" y2="19" />
 *    </svg>
 *    ```
 *    Inline SVG with proper accessibility attributes
 * 
 * 6. **Component Integration**:
 *    ```typescript
 *    {showToolbar && <CollapsibleToolbar />}
 *    ```
 *    Conditional integration of external components
 * 
 * Component Design Benefits:
 * - **Single Responsibility**: Only handles input control UI
 * - **Flexible Layout**: Conditional rendering for different configurations
 * - **State Visualization**: Clear visual feedback for different states
 * - **Accessibility**: Comprehensive ARIA labels and semantic buttons
 * - **Performance**: Minimal re-renders with optimized conditional logic
 * - **Integration**: Seamless CollapsibleToolbar integration
 * 
 * Button State Management:
 * - **File Button**: Disabled during sending, provides upload functionality
 * - **Send Button**: Multiple states (enabled, disabled, sending) with visual feedback
 * - **Toolbar**: Always available unless explicitly hidden
 * - **Visual Feedback**: Loading spinner, disabled states, hover effects
 * 
 * Icon Strategy:
 * - **Inline SVG**: Better performance than external icon files
 * - **Consistent Sizing**: Standardized width/height across buttons
 * - **Accessibility**: aria-hidden for decorative icons
 * - **Color Inheritance**: Uses currentColor for theme compatibility
 * 
 * Layout Considerations:
 * - **Corner Buttons**: Positioned above textarea for easy access
 * - **Send Button**: Adjacent to textarea for natural flow
 * - **Responsive Design**: Works on mobile and desktop
 * - **Z-index Management**: Proper layering for toolbar overlay
 * 
 * Accessibility Features:
 * - ARIA labels for screen readers
 * - Proper button semantics
 * - Keyboard navigation support
 * - Disabled state communication
 * - Loading state feedback
 * 
 * Integration with File Input:
 * ```typescript
 * // Parent component handles actual file input
 * const fileInputRef = useRef<HTMLInputElement>(null)
 * 
 * const handleFileSelect = () => {
 *   fileInputRef.current?.click()
 * }
 * 
 * <InputControls
 *   onFileSelect={handleFileSelect}
 *   onSendMessage={handleSendMessage}
 *   canSendMessage={canSendMessage}
 *   isSending={isSending}
 * />
 * 
 * <input
 *   ref={fileInputRef}
 *   type="file"
 *   hidden
 *   onChange={handleFileInputChange}
 * />
 * ```
 * 
 * This pattern separates UI controls from file handling logic,
 * making the component focused on presentation while enabling
 * flexible integration with different file handling strategies.
 */