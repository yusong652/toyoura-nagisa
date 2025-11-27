import React from 'react'
import { ThumbnailStripProps } from '../types'

/**
 * Thumbnail strip component for ImageViewer.
 * 
 * Displays a scrollable row of image thumbnails for quick navigation.
 * Automatically scrolls to keep the active thumbnail visible.
 * Only renders when multiple images are available.
 * 
 * Args:
 *     images: Array of image URLs for thumbnails
 *     imageNames: Optional names for accessibility
 *     currentIndex: Index of currently active image
 *     onImageSelect: Handler for thumbnail click
 *     thumbnailStripRef: Ref for the scrollable container
 *     activeThumbnailRef: Ref for the active thumbnail button
 * 
 * Returns:
 *     JSX.Element | null: Thumbnail strip or null for single images
 * 
 * TypeScript Learning Points:
 * - Array mapping with index for unique keys
 * - Conditional ref assignment with ternary operator
 * - Dynamic className construction
 * - Ref forwarding to specific elements
 */
const ThumbnailStrip: React.FC<ThumbnailStripProps> = ({
  images,
  imageNames,
  currentIndex,
  onImageSelect,
  thumbnailStripRef,
  activeThumbnailRef
}) => {
  // Don't render for single image
  if (images.length <= 1) {
    return null
  }

  return (
    <div className="thumbnail-strip" ref={thumbnailStripRef}>
      {images.map((image, index) => {
        const isActive = index === currentIndex
        const imageName = imageNames[index] || `Image ${index + 1}`
        
        return (
          <button
            key={index}
            ref={isActive ? activeThumbnailRef : null}
            className={`thumbnail ${isActive ? 'active' : ''}`}
            onClick={() => onImageSelect(index)}
            aria-label={`View ${imageName}`}
            title={imageName}
            type="button"
          >
            <img 
              src={image} 
              alt={`Thumbnail of ${imageName}`}
              loading="lazy"
              draggable={false}
            />
          </button>
        )
      })}
    </div>
  )
}

export default ThumbnailStrip

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Array Mapping with Index:
 *    images.map((image, index) => ...) for iteration
 * 
 * 2. Conditional Ref Assignment:
 *    ref={isActive ? activeThumbnailRef : null}
 * 
 * 3. Dynamic Class Names:
 *    Template literal for conditional active class
 * 
 * 4. Arrow Function in Props:
 *    onClick={() => onImageSelect(index)}
 * 
 * 5. Fallback Values:
 *    imageNames[index] || `Image ${index + 1}`
 * 
 * Benefits of This Component:
 * - Efficient thumbnail navigation for large galleries
 * - Lazy loading for performance
 * - Accessibility with proper labels and titles
 * - Auto-scrolling handled by parent hook
 * - Visual feedback for active thumbnail
 * - Keyboard navigation support
 * 
 * CSS Classes Expected:
 * - .thumbnail-strip: Horizontal scrollable container
 * - .thumbnail: Individual thumbnail button
 * - .thumbnail.active: Active state styling
 * - Hover and focus states for accessibility
 * 
 * Performance Notes:
 * - Uses loading="lazy" for off-screen thumbnails
 * - Keys are based on stable array indices
 * - Refs only assigned when needed (active thumbnail)
 */