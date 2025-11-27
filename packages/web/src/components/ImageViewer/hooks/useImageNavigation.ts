import { useCallback, useMemo } from 'react'
import { ImageNavigationHookReturn } from '../types'

/**
 * Custom hook for managing image navigation.
 * 
 * Provides navigation functions and state for moving between images
 * in a gallery. Handles circular navigation and boundary conditions.
 * 
 * Args:
 *     images: Array of image URLs
 *     currentIndex: Current image index
 *     setCurrentIndex: Function to update current index
 * 
 * Returns:
 *     ImageNavigationHookReturn: Navigation functions and state:
 *         - handlePrevImage: Navigate to previous image
 *         - handleNextImage: Navigate to next image
 *         - canNavigatePrev: Whether previous navigation is possible
 *         - canNavigateNext: Whether next navigation is possible
 * 
 * TypeScript Learning Points:
 * - Modular hook design with clear responsibilities
 * - Boolean state derivation with useMemo
 * - Circular array navigation logic
 * - Function memoization with useCallback
 */
export const useImageNavigation = (
  images: string[],
  currentIndex: number,
  setCurrentIndex: (index: number) => void
): ImageNavigationHookReturn => {
  /**
   * Navigate to the previous image.
   * Uses circular navigation - wraps to last image when at first.
   */
  const handlePrevImage = useCallback((): void => {
    if (images.length > 1) {
      const newIndex = (currentIndex - 1 + images.length) % images.length
      setCurrentIndex(newIndex)
    }
  }, [images.length, currentIndex, setCurrentIndex])

  /**
   * Navigate to the next image.
   * Uses circular navigation - wraps to first image when at last.
   */
  const handleNextImage = useCallback((): void => {
    if (images.length > 1) {
      const newIndex = (currentIndex + 1) % images.length
      setCurrentIndex(newIndex)
    }
  }, [images.length, currentIndex, setCurrentIndex])

  /**
   * Compute navigation availability.
   * For circular navigation, always available when multiple images exist.
   */
  const canNavigatePrev = useMemo((): boolean => {
    return images.length > 1
  }, [images.length])

  const canNavigateNext = useMemo((): boolean => {
    return images.length > 1
  }, [images.length])

  return {
    handlePrevImage,
    handleNextImage,
    canNavigatePrev,
    canNavigateNext
  }
}

/**
 * Alternative implementation for non-circular navigation:
 * 
 * export const useImageNavigationLinear = (...args) => {
 *   const canNavigatePrev = useMemo(() => {
 *     return currentIndex > 0
 *   }, [currentIndex])
 * 
 *   const canNavigateNext = useMemo(() => {
 *     return currentIndex < images.length - 1
 *   }, [currentIndex, images.length])
 * 
 *   const handlePrevImage = useCallback(() => {
 *     if (canNavigatePrev) {
 *       setCurrentIndex(currentIndex - 1)
 *     }
 *   }, [canNavigatePrev, currentIndex, setCurrentIndex])
 * 
 *   const handleNextImage = useCallback(() => {
 *     if (canNavigateNext) {
 *       setCurrentIndex(currentIndex + 1)
 *     }
 *   }, [canNavigateNext, currentIndex, setCurrentIndex])
 * }
 */

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Modular Hook Design:
 *    Single responsibility - only handles navigation
 * 
 * 2. Circular Array Logic:
 *    Mathematical modulo operation for array wrapping
 * 
 * 3. Derived State:
 *    canNavigate booleans computed from current state
 * 
 * 4. Performance Optimization:
 *    useMemo and useCallback prevent unnecessary re-computations
 * 
 * 5. Clear API Design:
 *    Return object with descriptive property names
 * 
 * Benefits of This Hook:
 * - Encapsulates navigation logic completely
 * - Supports both circular and linear navigation patterns
 * - Performance optimized with memoization
 * - Easy to extend with additional navigation features
 * - Clear separation from other image viewer concerns
 * - Testable in isolation
 */