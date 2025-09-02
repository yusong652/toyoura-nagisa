import React from 'react'
import { ImageContainerProps } from '../types'
import LoadingOverlay from './LoadingOverlay'

/**
 * Container component for the main image display.
 * 
 * Handles image rendering with loading states, zoom/pan transforms,
 * and all interaction event handling. Provides the main viewport
 * for image viewing with proper aspect ratio handling.
 * 
 * Args:
 *     currentImage: URL of current image to display
 *     currentImageName: Alt text for the image
 *     isLoading: Whether image is currently loading
 *     zoom: Current zoom level
 *     pan: Current pan position
 *     isDragging: Whether user is currently dragging
 *     onImageLoad: Handler when image finishes loading
 *     onImageError: Handler when image fails to load
 *     onMouseDown/Move/Up/Leave: Mouse interaction handlers
 *     onWheel: Mouse wheel zoom handler
 *     onTouchStart/Move/End: Touch interaction handlers
 *     containerStyle: Dynamic container styles
 *     imageStyle: Dynamic image transform styles
 * 
 * Returns:
 *     JSX.Element: Image container with loading overlay and interactions
 * 
 * TypeScript Learning Points:
 * - Complex props interface with event handlers
 * - Dynamic style application from props
 * - Conditional rendering for loading states
 * - Event handler prop passing
 */
const ImageContainer: React.FC<ImageContainerProps> = ({
  currentImage,
  currentImageName,
  isLoading,
  zoom,
  // pan and isDragging are used in the style objects passed as props
  pan: _pan,
  isDragging: _isDragging,
  onImageLoad,
  onImageError,
  onMouseDown,
  onMouseMove,
  onMouseUp,
  onMouseLeave,
  onWheel,
  onTouchStart,
  onTouchMove,
  onTouchEnd,
  containerStyle,
  imageStyle
}) => {
  return (
    <div 
      className="image-container"
      onWheel={onWheel}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={onMouseLeave}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
      style={containerStyle}
      role="img"
      aria-label={`Image viewer: ${currentImageName}`}
    >
      {/* Loading overlay */}
      <LoadingOverlay isLoading={isLoading} />
      
      {/* Main image */}
      <img
        src={currentImage}
        alt={currentImageName}
        className="viewer-image"
        onLoad={onImageLoad}
        onError={onImageError}
        style={{
          ...imageStyle,
          opacity: isLoading ? 0 : 1
        }}
        draggable={false}
      />
      
      {/* Zoom level indicator (optional) */}
      {zoom !== 1 && !isLoading && (
        <div className="zoom-indicator-overlay">
          {Math.round(zoom * 100)}%
        </div>
      )}
    </div>
  )
}

export default ImageContainer

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Complex Props Interface:
 *    Multiple event handlers with proper typing
 * 
 * 2. Dynamic Styling:
 *    Style objects passed as props and merged
 * 
 * 3. Conditional Rendering:
 *    Multiple conditional elements based on state
 * 
 * 4. Event Handler Composition:
 *    All interaction events handled in one container
 * 
 * 5. Style Merging:
 *    Combining dynamic styles with additional properties
 * 
 * Benefits of This Component:
 * - Centralized image interaction handling
 * - Clean separation of image display logic
 * - Loading state management
 * - Accessibility with proper ARIA roles
 * - Performance optimized with conditional rendering
 * - Flexible styling through props
 * 
 * CSS Classes Expected:
 * - .image-container: Main container with flex centering
 * - .viewer-image: Image with transform and transition
 * - .zoom-indicator-overlay: Optional zoom level display
 */