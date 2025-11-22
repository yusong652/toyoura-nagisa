import { useState, useEffect, useCallback, useMemo } from 'react'
import { 
  ImageViewerStateHookReturn, 
  PanPosition, 
  DEFAULT_ZOOM_CONSTRAINTS 
} from '../types'

/**
 * Custom hook for managing ImageViewer core state.
 * 
 * Handles image navigation, zoom levels, pan positions, and loading states.
 * Provides computed values and state management for the image viewer component.
 * 
 * Args:
 *     images: Array of image URLs
 *     imageNames: Optional array of image names
 *     initialIndex: Starting image index
 *     open: Whether the viewer is open
 * 
 * Returns:
 *     ImageViewerStateHookReturn: Complete state management object:
 *         - currentIndex: Active image index
 *         - setCurrentIndex: Update current image
 *         - zoom: Current zoom level
 *         - setZoom: Update zoom level
 *         - pan: Current pan position
 *         - setPan: Update pan position
 *         - isLoading: Loading state
 *         - setIsLoading: Update loading state
 *         - currentImage: Current image URL
 *         - hasMultipleImages: Whether there are multiple images
 *         - getCurrentImageName: Get current image name
 * 
 * TypeScript Learning Points:
 * - Complex state management with multiple interdependent states
 * - useMemo for expensive computations
 * - useCallback for stable function references
 * - Generic type constraints for flexible APIs
 */
export const useImageViewerState = (
  images: string[],
  imageNames: string[] = [],
  initialIndex: number = 0,
  open: boolean = false
): ImageViewerStateHookReturn => {
  // Core state management
  const [currentIndex, setCurrentIndex] = useState(initialIndex)
  const [zoom, setZoom] = useState(1)
  const [pan, setPan] = useState<PanPosition>({ x: 0, y: 0 })
  const [isLoading, setIsLoading] = useState(true)

  // Reset state when viewer opens/closes or initial index changes
  useEffect(() => {
    if (open) {
      setCurrentIndex(initialIndex)
      setZoom(1)
      setPan({ x: 0, y: 0 })
      setIsLoading(true)
    }
  }, [open, initialIndex])

  // Reset zoom and pan when image changes
  useEffect(() => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
    setIsLoading(true)
  }, [currentIndex])

  // Computed values with memoization
  const currentImage = useMemo(() => {
    return images[currentIndex] || ''
  }, [images, currentIndex])

  const hasMultipleImages = useMemo(() => {
    return images.length > 1
  }, [images.length])

  /**
   * Get the display name for the current image.
   * Uses provided name or falls back to index-based name.
   */
  const getCurrentImageName = useCallback((): string => {
    return imageNames[currentIndex] || `Image ${currentIndex + 1}`
  }, [imageNames, currentIndex])

  /**
   * Enhanced setCurrentIndex with bounds checking.
   * Ensures index is always within valid range.
   */
  const setCurrentIndexSafe = useCallback((index: number): void => {
    if (index >= 0 && index < images.length) {
      setCurrentIndex(index)
    }
  }, [images.length])

  /**
   * Enhanced setZoom with constraints.
   * Automatically clamps zoom to valid range.
   */
  const setZoomSafe = useCallback((
    zoomValue: number | ((prev: number) => number)
  ): void => {
    setZoom(prev => {
      const newZoom = typeof zoomValue === 'function' ? zoomValue(prev) : zoomValue
      return Math.min(Math.max(newZoom, DEFAULT_ZOOM_CONSTRAINTS.min), DEFAULT_ZOOM_CONSTRAINTS.max)
    })
  }, [])

  return {
    currentIndex,
    setCurrentIndex: setCurrentIndexSafe,
    zoom,
    setZoom: setZoomSafe,
    pan,
    setPan,
    isLoading,
    setIsLoading,
    currentImage,
    hasMultipleImages,
    getCurrentImageName
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Complex State Management:
 *    Multiple useState hooks with interdependent effects
 * 
 * 2. Function Overloading:
 *    setZoom accepts both values and updater functions
 * 
 * 3. useMemo for Performance:
 *    Expensive computations cached until dependencies change
 * 
 * 4. useCallback Stability:
 *    Function references remain stable across renders
 * 
 * 5. Generic Constraints:
 *    Type parameters constrained for specific use cases
 * 
 * Benefits of This Hook:
 * - Centralized state management for image viewer
 * - Automatic bounds checking and constraint enforcement
 * - Performance optimized with memoization
 * - Clear separation between state and business logic
 * - Easy to test in isolation
 * - Prevents common state-related bugs
 */