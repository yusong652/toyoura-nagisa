import React from 'react'
import { useMediaModal, usePreventBodyScroll } from './hooks'
import MediaModalContainer from './components/MediaModalContainer'
import MediaModalHeader from './components/MediaModalHeader'
import { MediaModalProps } from './types'
import './MediaModal.css'

/**
 * Base MediaModal component for all media viewers.
 * 
 * Provides common modal functionality including overlay, escape key handling,
 * body scroll prevention, and consistent structure. Designed to be extended
 * by specific media viewers (ImageViewer, VideoPlayer, etc.).
 * 
 * Args:
 *     open: Whether modal is visible
 *     onClose: Handler to close modal
 *     children: Modal content
 *     className: Additional CSS classes
 *     title: Optional header title
 *     showCloseButton: Whether to show close button
 *     preventBackgroundClose: Disable overlay click to close
 *     preventEscapeClose: Disable escape key to close
 * 
 * Returns:
 *     JSX.Element | null: Modal component or null when closed
 * 
 * TypeScript Learning Points:
 * - Component composition with children
 * - Custom hook integration
 * - Conditional rendering
 * - Props destructuring with defaults
 * 
 * Architecture Benefits:
 * - Centralized modal behavior
 * - Consistent UX patterns
 * - Easy to extend for specific use cases
 * - Clean separation of concerns
 */
const MediaModal: React.FC<MediaModalProps> = ({
  open,
  onClose,
  children,
  className = '',
  title,
  showCloseButton = true,
  preventBackgroundClose = false,
  preventEscapeClose = false
}) => {
  // Core modal behavior hooks
  const { 
    handleBackgroundClick, 
    handleContainerClick 
  } = useMediaModal(
    open,
    onClose,
    preventBackgroundClose,
    preventEscapeClose
  )
  
  // Prevent body scrolling when modal is open
  usePreventBodyScroll({
    enabled: open,
    restoreOnUnmount: true
  })
  
  // Don't render if not open
  if (!open) {
    return null
  }
  
  return (
    <div 
      className={`media-modal-overlay ${className}`}
      onClick={handleBackgroundClick}
      role="presentation"
    >
      <MediaModalContainer 
        onClick={handleContainerClick}
        className={className ? `${className}-container` : ''}
      >
        {(title || showCloseButton) && (
          <MediaModalHeader
            title={title}
            onClose={onClose}
            showCloseButton={showCloseButton}
          />
        )}
        
        <div className="media-modal-content">
          {children}
        </div>
      </MediaModalContainer>
    </div>
  )
}

export default MediaModal

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. React.FC with Generic Props:
 *    React.FC<MediaModalProps> provides type safety
 * 
 * 2. Hook Composition:
 *    Multiple hooks provide modular functionality
 * 
 * 3. Conditional Rendering:
 *    Early return and && operator for conditional elements
 * 
 * 4. Props with Defaults:
 *    Destructuring with = for default values
 * 
 * 5. Template Literals:
 *    Dynamic className construction
 * 
 * Usage Examples:
 * 
 * Basic modal:
 * ```typescript
 * <MediaModal open={isOpen} onClose={handleClose}>
 *   <img src={imageUrl} alt="Preview" />
 * </MediaModal>
 * ```
 * 
 * With header:
 * ```typescript
 * <MediaModal 
 *   open={isOpen} 
 *   onClose={handleClose}
 *   title="Image Preview"
 * >
 *   <ImageContent />
 * </MediaModal>
 * ```
 * 
 * Prevent closing:
 * ```typescript
 * <MediaModal 
 *   open={isOpen} 
 *   onClose={handleClose}
 *   preventBackgroundClose
 *   preventEscapeClose
 * >
 *   <CriticalContent />
 * </MediaModal>
 * ```
 * 
 * Architecture Notes:
 * - This component provides the base structure
 * - Specific viewers extend this with their own logic
 * - Hooks handle all side effects and interactions
 * - CSS provides visual styling (see MediaModal.css)
 */