import React from 'react'
import { LoadingOverlayProps } from '../types'

/**
 * Loading overlay component for ImageViewer.
 * 
 * Displays a loading spinner and message while images are loading.
 * Uses a centered overlay design with smooth fade in/out animations.
 * 
 * Args:
 *     isLoading: Whether to show the loading overlay
 *     message: Optional loading message (defaults to "Loading image...")
 * 
 * Returns:
 *     JSX.Element | null: Loading overlay or null when not loading
 * 
 * TypeScript Learning Points:
 * - Early return pattern for conditional rendering
 * - Default parameter values
 * - Simple props interface design
 */
const LoadingOverlay: React.FC<LoadingOverlayProps> = ({
  isLoading,
  message = "Loading image..."
}) => {
  if (!isLoading) {
    return null
  }

  return (
    <div className="image-loading">
      <div className="loading-spinner" />
      <span className="loading-message">{message}</span>
    </div>
  )
}

export default LoadingOverlay

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Early Return Pattern:
 *    Returns null when component shouldn't render
 * 
 * 2. Default Parameters:
 *    message = "Loading image..." provides fallback
 * 
 * 3. Conditional Component:
 *    Entire component can be null or JSX
 * 
 * 4. Simple Props Interface:
 *    Minimal, focused component responsibility
 * 
 * Benefits of This Component:
 * - Reusable loading UI pattern
 * - Consistent loading experience
 * - Minimal props for easy usage
 * - Performance optimized with early returns
 * - Easy to customize via CSS
 * 
 * CSS Classes Expected:
 * - .image-loading: Overlay container with centering
 * - .loading-spinner: Animated spinner element
 * - .loading-message: Text styling for loading message
 */