import React from 'react'
import { ImageNavigationProps } from '../types'

/**
 * Navigation arrows component for ImageViewer.
 * 
 * Provides previous and next navigation buttons positioned on the sides
 * of the image. Only renders when multiple images are available and can
 * be hidden/shown based on user activity.
 * 
 * Args:
 *     hasMultipleImages: Whether navigation should be shown
 *     canNavigatePrev: Whether previous navigation is enabled
 *     canNavigateNext: Whether next navigation is enabled
 *     onPrevImage: Handler for previous image button
 *     onNextImage: Handler for next image button
 *     visible: Whether navigation controls should be visible (auto-hide support)
 *     className: Additional CSS classes for styling
 * 
 * Returns:
 *     JSX.Element | null: Navigation arrows or null when not needed/visible
 * 
 * TypeScript Learning Points:
 * - Early return for conditional component rendering
 * - Fragment wrapper for multiple elements  
 * - Boolean props for conditional functionality
 * - Consistent SVG icon patterns
 * - CSS class composition with visibility control
 */
const ImageNavigation: React.FC<ImageNavigationProps> = ({
  hasMultipleImages,
  canNavigatePrev,
  canNavigateNext,
  onPrevImage,
  onNextImage,
  className = ''
}) => {
  // Don't render when not needed
  if (!hasMultipleImages) {
    return null
  }

  return (
    <>
      {/* Previous Image Button */}
      <button 
        className={`nav-btn prev-btn ${className}`.trim()} 
        onClick={onPrevImage}
        disabled={!canNavigatePrev}
        aria-label="Previous image"
        type="button"
      >
        <svg 
          width="20" 
          height="20" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M15 18L9 12l6-6"/>
        </svg>
      </button>
      
      {/* Next Image Button */}
      <button 
        className={`nav-btn next-btn ${className}`.trim()} 
        onClick={onNextImage}
        disabled={!canNavigateNext}
        aria-label="Next image"
        type="button"
      >
        <svg 
          width="20" 
          height="20" 
          viewBox="0 0 24 24" 
          fill="none" 
          stroke="currentColor" 
          strokeWidth="2" 
          strokeLinecap="round" 
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M9 18l6-6-6-6"/>
        </svg>
      </button>
    </>
  )
}

export default ImageNavigation

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Conditional Component:
 *    Early return null when not needed
 * 
 * 2. React Fragment:
 *    <> wrapper for multiple elements without extra DOM
 * 
 * 3. Boolean Props:
 *    hasMultipleImages, canNavigate* for state control
 * 
 * 4. Consistent SVG Patterns:
 *    Standardized SVG properties across icons
 * 
 * 5. Accessibility Compliance:
 *    aria-label for screen readers, type="button"
 * 
 * Benefits of This Component:
 * - Only renders when needed (multiple images)
 * - Consistent navigation UI pattern
 * - Proper accessibility support
 * - Clean conditional rendering
 * - Reusable across different gallery contexts
 * 
 * CSS Classes Expected:
 * - .nav-btn: Base navigation button styles
 * - .prev-btn: Left-side positioning for previous
 * - .next-btn: Right-side positioning for next
 * - Hover and disabled states for both
 */