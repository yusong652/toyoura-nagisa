import { useRef, useEffect, useCallback } from 'react'
import { ThumbnailNavigationHookReturn } from '../types'

/**
 * Custom hook for managing thumbnail strip navigation.
 * 
 * Handles automatic scrolling of thumbnail strip to keep the active
 * thumbnail visible, smooth scroll animations, and ref management
 * for DOM manipulation.
 * 
 * Args:
 *     currentIndex: Index of currently active image
 *     totalImages: Total number of images
 *     open: Whether the viewer is open
 * 
 * Returns:
 *     ThumbnailNavigationHookReturn: Thumbnail navigation utilities:
 *         - thumbnailStripRef: Ref for thumbnail strip container
 *         - activeThumbnailRef: Ref for currently active thumbnail
 *         - scrollToActiveThumbnail: Manual scroll trigger function
 * 
 * TypeScript Learning Points:
 * - useRef with specific DOM element types
 * - DOM manipulation with getBoundingClientRect
 * - Smooth scroll API with scrollTo
 * - Effect cleanup with timeouts
 */
export const useThumbnailNavigation = (
  currentIndex: number,
  totalImages: number,
  open: boolean
): ThumbnailNavigationHookReturn => {
  const thumbnailStripRef = useRef<HTMLDivElement>(null)
  const activeThumbnailRef = useRef<HTMLButtonElement>(null)

  /**
   * Scroll the thumbnail strip to center the active thumbnail.
   * Uses smooth scrolling with proper bounds checking.
   */
  const scrollToActiveThumbnail = useCallback((): void => {
    if (!thumbnailStripRef.current || !activeThumbnailRef.current) return

    const thumbnail = activeThumbnailRef.current
    const strip = thumbnailStripRef.current
    
    try {
      const thumbnailRect = thumbnail.getBoundingClientRect()
      const stripRect = strip.getBoundingClientRect()
      
      // Calculate the center position for the thumbnail
      const thumbnailCenter = thumbnail.offsetLeft + thumbnailRect.width / 2
      const stripCenter = stripRect.width / 2
      
      // Calculate scroll position to center the thumbnail
      const scrollLeft = thumbnailCenter - stripCenter
      
      // Smooth scroll to the calculated position
      strip.scrollTo({
        left: Math.max(0, scrollLeft),
        behavior: 'smooth'
      })
    } catch (error) {
      // Fallback to instant scroll if smooth scroll fails
      console.warn('Smooth scroll failed, using instant scroll:', error)
      const scrollLeft = thumbnail.offsetLeft - stripRect.width / 2
      strip.scrollLeft = Math.max(0, scrollLeft)
    }
  }, [])

  /**
   * Auto-scroll to active thumbnail when current index changes.
   * Uses a small delay to ensure DOM is fully rendered.
   */
  useEffect(() => {
    if (!open || totalImages <= 1) return

    // Small delay to ensure DOM elements are properly rendered
    const scrollTimeout = setTimeout(() => {
      scrollToActiveThumbnail()
    }, 100)

    return () => clearTimeout(scrollTimeout)
  }, [currentIndex, open, totalImages, scrollToActiveThumbnail])

  /**
   * Initial scroll setup when viewer opens.
   * Ensures the initial image is visible without animation.
   */
  useEffect(() => {
    if (!open || !thumbnailStripRef.current || !activeThumbnailRef.current) return

    // Immediate scroll without animation for initial load
    const thumbnail = activeThumbnailRef.current
    const strip = thumbnailStripRef.current
    
    try {
      const thumbnailRect = thumbnail.getBoundingClientRect()
      const stripRect = strip.getBoundingClientRect()
      const scrollLeft = thumbnail.offsetLeft - stripRect.width / 2
      
      // Instant scroll for initial positioning
      strip.scrollLeft = Math.max(0, scrollLeft)
    } catch (error) {
      // Silently fail for initial positioning
    }
  }, [open])

  return {
    thumbnailStripRef,
    activeThumbnailRef,
    scrollToActiveThumbnail
  }
}

/**
 * Extended thumbnail navigation with additional features:
 * 
 * export const useThumbnailNavigationAdvanced = (...args) => {
 *   const baseHook = useThumbnailNavigation(...args)
 *   
 *   // Add keyboard navigation
 *   const handleKeyboardNavigation = useCallback((e: KeyboardEvent) => {
 *     if (e.key === 'Home') {
 *       // Scroll to first thumbnail
 *       if (thumbnailStripRef.current) {
 *         thumbnailStripRef.current.scrollTo({ left: 0, behavior: 'smooth' })
 *       }
 *     } else if (e.key === 'End') {
 *       // Scroll to last thumbnail
 *       if (thumbnailStripRef.current) {
 *         thumbnailStripRef.current.scrollTo({ 
 *           left: thumbnailStripRef.current.scrollWidth, 
 *           behavior: 'smooth' 
 *         })
 *       }
 *     }
 *   }, [])
 * 
 *   // Add scroll indicators
 *   const [canScrollLeft, setCanScrollLeft] = useState(false)
 *   const [canScrollRight, setCanScrollRight] = useState(false)
 * 
 *   const updateScrollIndicators = useCallback(() => {
 *     if (!thumbnailStripRef.current) return
 * 
 *     const { scrollLeft, scrollWidth, clientWidth } = thumbnailStripRef.current
 *     setCanScrollLeft(scrollLeft > 0)
 *     setCanScrollRight(scrollLeft < scrollWidth - clientWidth)
 *   }, [])
 * 
 *   return {
 *     ...baseHook,
 *     handleKeyboardNavigation,
 *     canScrollLeft,
 *     canScrollRight,
 *     updateScrollIndicators
 *   }
 * }
 */

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Specific DOM Element Refs:
 *    useRef<HTMLDivElement> and useRef<HTMLButtonElement>
 * 
 * 2. DOM API Integration:
 *    getBoundingClientRect(), scrollTo(), offsetLeft
 * 
 * 3. Error Handling:
 *    try/catch for DOM operations that might fail
 * 
 * 4. Effect Dependencies:
 *    Careful dependency arrays for proper effect triggering
 * 
 * 5. Timeout Management:
 *    setTimeout with cleanup in useEffect
 * 
 * Benefits of This Hook:
 * - Automatic thumbnail visibility management
 * - Smooth scroll animations with fallbacks
 * - Performance optimized with delays and cleanup
 * - Handles edge cases (no thumbnails, single image)
 * - Separates thumbnail logic from main component
 * - Easy to extend with additional features
 * - Robust error handling for DOM operations
 */