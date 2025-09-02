import React from 'react'
import { ImageViewerHeaderProps } from '../types'

/**
 * Header component for ImageViewer.
 * 
 * Displays image information (name and counter) and provides a close button.
 * Uses a gradient background for better text visibility over images.
 * 
 * Args:
 *     currentImageName: Display name of current image
 *     currentIndex: Zero-based index of current image
 *     totalImages: Total number of images in the gallery
 *     onClose: Handler for close button click
 *     hasMultipleImages: Whether to show image counter
 * 
 * Returns:
 *     JSX.Element: Header with image info and close button
 * 
 * TypeScript Learning Points:
 * - Component props destructuring
 * - Conditional rendering with logical AND operator
 * - SVG icons in JSX with proper accessibility
 * - Button event handling
 */
const ImageViewerHeader: React.FC<ImageViewerHeaderProps> = ({
  currentImageName,
  currentIndex,
  totalImages,
  onClose,
  hasMultipleImages
}) => {
  return (
    <div className="image-viewer-header">
      <div className="image-info">
        <span className="image-name">{currentImageName}</span>
        {hasMultipleImages && (
          <span className="image-counter">
            {currentIndex + 1} of {totalImages}
          </span>
        )}
      </div>
      
      <button 
        className="close-btn" 
        onClick={onClose} 
        aria-label="Close image viewer"
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
    </div>
  )
}

export default ImageViewerHeader

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Props Destructuring:
 *    Clean parameter extraction from props object
 * 
 * 2. Conditional Rendering:
 *    hasMultipleImages && <Component> pattern
 * 
 * 3. Accessibility Attributes:
 *    aria-label, aria-hidden, type="button"
 * 
 * 4. SVG Integration:
 *    Type-safe SVG properties with currentColor
 * 
 * Benefits of This Component:
 * - Single responsibility (header display only)
 * - Consistent close button styling
 * - Accessibility compliant
 * - Clean conditional rendering
 * - Reusable across different image viewer contexts
 * 
 * CSS Classes Expected:
 * - .image-viewer-header: Container with gradient background
 * - .image-info: Text information container
 * - .image-name: Main image title styling
 * - .image-counter: Secondary counter text styling
 * - .close-btn: Close button with hover states
 */