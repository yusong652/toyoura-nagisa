import React from 'react'
import { MediaModalContainerProps } from '../types'

/**
 * Container component for media modal content.
 * 
 * Provides the inner container that holds modal content and prevents
 * click propagation to the overlay. Supports custom styling while
 * maintaining consistent modal behavior.
 * 
 * Args:
 *     children: Modal content to display
 *     className: Additional CSS classes for styling
 *     onClick: Optional click handler for container
 * 
 * Returns:
 *     JSX.Element: Container div with proper event handling
 * 
 * TypeScript Learning Points:
 * - ReactNode type for flexible children
 * - Optional props with conditional rendering
 * - Event handler typing
 */
const MediaModalContainer: React.FC<MediaModalContainerProps> = ({
  children,
  className = '',
  onClick
}) => {
  const handleClick = (e: React.MouseEvent) => {
    // Always stop propagation to prevent closing
    e.stopPropagation()
    
    // Call custom handler if provided
    if (onClick) {
      onClick(e)
    }
  }
  
  return (
    <div 
      className={`media-modal-container ${className}`}
      onClick={handleClick}
      role="dialog"
      aria-modal="true"
    >
      {children}
    </div>
  )
}

export default MediaModalContainer

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. ReactNode Type:
 *    Accepts any valid React child (elements, strings, numbers, etc.)
 * 
 * 2. Default Parameters:
 *    className = '' provides safe default for string concatenation
 * 
 * 3. Event Propagation:
 *    e.stopPropagation() prevents event bubbling
 * 
 * 4. Accessibility Attributes:
 *    role and aria-modal for screen readers
 * 
 * Benefits of This Component:
 * - Consistent click behavior across all modals
 * - Prevents accidental modal closure
 * - Flexible styling with className prop
 * - Accessibility features built-in
 * - Simple, focused responsibility
 */