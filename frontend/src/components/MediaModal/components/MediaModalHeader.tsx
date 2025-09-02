import React from 'react'
import { MediaModalHeaderProps } from '../types'

/**
 * Header component for media modals.
 * 
 * Provides a consistent header layout with title, subtitle, and close button.
 * Supports customization while maintaining standard modal header patterns.
 * 
 * Args:
 *     title: Main header title
 *     subtitle: Optional subtitle or metadata
 *     onClose: Handler for close button click
 *     showCloseButton: Whether to display close button
 *     className: Additional CSS classes
 * 
 * Returns:
 *     JSX.Element | null: Header component or null if no content
 * 
 * TypeScript Learning Points:
 * - Conditional rendering with early returns
 * - Optional props with defaults
 * - SVG icon components
 * - Accessibility labels
 */
const MediaModalHeader: React.FC<MediaModalHeaderProps> = ({
  title,
  subtitle,
  onClose,
  showCloseButton = true,
  className = ''
}) => {
  // Don't render if no content
  if (!title && !subtitle && !showCloseButton) {
    return null
  }
  
  return (
    <div className={`media-modal-header ${className}`}>
      <div className="media-modal-header-content">
        {title && (
          <h2 className="media-modal-title">{title}</h2>
        )}
        {subtitle && (
          <span className="media-modal-subtitle">{subtitle}</span>
        )}
      </div>
      
      {showCloseButton && (
        <button 
          className="media-modal-close-btn" 
          onClick={onClose}
          aria-label="Close modal"
          type="button"
        >
          <svg 
            width="24" 
            height="24" 
            viewBox="0 0 24 24" 
            fill="none"
            aria-hidden="true"
          >
            <path 
              d="M18 6L6 18M6 6l12 12" 
              stroke="currentColor" 
              strokeWidth="2" 
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </button>
      )}
    </div>
  )
}

export default MediaModalHeader

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Early Return Pattern:
 *    Returns null when no content to render
 * 
 * 2. Conditional Rendering:
 *    title && <h2>... pattern for optional elements
 * 
 * 3. Default Props:
 *    showCloseButton = true for common use case
 * 
 * 4. SVG in JSX:
 *    Type-safe SVG properties with TypeScript
 * 
 * 5. Button Type Attribute:
 *    type="button" prevents form submission
 * 
 * Benefits of This Component:
 * - Consistent header layout across modals
 * - Flexible content with title and subtitle
 * - Accessibility-compliant close button
 * - Clean separation of header concerns
 * - Optimized rendering with early returns
 * 
 * CSS Classes Expected:
 * - .media-modal-header: Container styles
 * - .media-modal-header-content: Title/subtitle wrapper
 * - .media-modal-title: Title typography
 * - .media-modal-subtitle: Subtitle typography
 * - .media-modal-close-btn: Close button styles
 */