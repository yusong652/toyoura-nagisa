import { useState, useCallback, useMemo } from 'react'
import { 
  ImageInteractionHookReturn, 
  PanPosition, 
  DragState, 
  TouchState,
  DEFAULT_SWIPE_THRESHOLD 
} from '../types'

/**
 * Custom hook for managing image interaction (mouse, touch, keyboard).
 * 
 * Handles complex user interactions including:
 * - Mouse dragging for panning
 * - Mouse wheel zooming  
 * - Touch gestures (pan, pinch, swipe)
 * - Dynamic cursor and style management
 * 
 * Args:
 *     zoom: Current zoom level
 *     setZoom: Function to update zoom level
 *     pan: Current pan position
 *     setPan: Function to update pan position
 *     onPrevImage: Handler for previous image navigation
 *     onNextImage: Handler for next image navigation
 * 
 * Returns:
 *     ImageInteractionHookReturn: Complete interaction handling:
 *         - isDragging: Whether user is currently dragging
 *         - handleMouseDown/Move/Up: Mouse event handlers
 *         - handleWheel: Mouse wheel zoom handler
 *         - handleTouchStart/Move/End: Touch gesture handlers
 *         - containerStyle: Dynamic styles for container
 *         - imageStyle: Dynamic styles for image transform
 * 
 * TypeScript Learning Points:
 * - Complex event handler typing
 * - State machine patterns for interaction states
 * - Mathematical calculations for gestures
 * - Dynamic style generation with React.CSSProperties
 */
export const useImageInteraction = (
  zoom: number,
  setZoom: (zoom: number | ((prev: number) => number)) => void,
  pan: PanPosition,
  setPan: (pan: PanPosition | ((prev: PanPosition) => PanPosition)) => void,
  onPrevImage: () => void,
  onNextImage: () => void
): ImageInteractionHookReturn => {
  // Interaction state
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState<DragState>({ x: 0, y: 0 })
  const [touchStart, setTouchStart] = useState<TouchState>({ x: 0, y: 0 })
  const [lastTouchDistance, setLastTouchDistance] = useState(0)

  /**
   * Calculate distance between two touch points for pinch gestures.
   */
  const getTouchDistance = useCallback((touches: React.TouchList): number => {
    if (touches.length < 2) return 0
    const touch1 = touches[0]
    const touch2 = touches[1]
    return Math.sqrt(
      Math.pow(touch2.clientX - touch1.clientX, 2) +
      Math.pow(touch2.clientY - touch1.clientY, 2)
    )
  }, [])

  /**
   * Mouse down handler - start dragging if zoomed.
   */
  const handleMouseDown = useCallback((e: React.MouseEvent): void => {
    if (zoom > 1) {
      setIsDragging(true)
      setDragStart({
        x: e.clientX - pan.x,
        y: e.clientY - pan.y
      })
    }
  }, [zoom, pan])

  /**
   * Mouse move handler - update pan position while dragging.
   */
  const handleMouseMove = useCallback((e: React.MouseEvent): void => {
    if (isDragging && zoom > 1) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
    }
  }, [isDragging, zoom, dragStart, setPan])

  /**
   * Mouse up handler - stop dragging.
   */
  const handleMouseUp = useCallback((): void => {
    setIsDragging(false)
  }, [])

  /**
   * Mouse wheel handler - zoom with Ctrl/Cmd key.
   */
  const handleWheel = useCallback((e: React.WheelEvent): void => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault()
      const delta = e.deltaY > 0 ? 0.9 : 1.1
      setZoom(prev => {
        const newZoom = prev * delta
        // Clamp zoom to valid range
        return Math.min(Math.max(newZoom, 0.1), 5)
      })
    }
  }, [setZoom])

  /**
   * Touch start handler - handle both single touch (pan/swipe) and multi-touch (pinch).
   */
  const handleTouchStart = useCallback((e: React.TouchEvent): void => {
    if (e.touches.length === 1) {
      // Single touch - potential swipe or pan
      const touch = e.touches[0]
      setTouchStart({ x: touch.clientX, y: touch.clientY })
    } else if (e.touches.length === 2) {
      // Two fingers - pinch gesture
      const distance = getTouchDistance(e.touches)
      setLastTouchDistance(distance)
    }
  }, [getTouchDistance])

  /**
   * Touch move handler - handle pan and pinch gestures.
   */
  const handleTouchMove = useCallback((e: React.TouchEvent): void => {
    e.preventDefault()
    
    if (e.touches.length === 1) {
      // Single touch - pan or swipe detection
      const touch = e.touches[0]
      const deltaX = touch.clientX - touchStart.x
      const deltaY = touch.clientY - touchStart.y
      
      if (zoom > 1) {
        // Pan when zoomed
        setPan(prevPan => ({
          x: prevPan.x + deltaX,
          y: prevPan.y + deltaY
        }))
        setTouchStart({ x: touch.clientX, y: touch.clientY })
      }
    } else if (e.touches.length === 2) {
      // Two fingers - pinch zoom
      const currentDistance = getTouchDistance(e.touches)
      const distanceChange = Math.abs(currentDistance - lastTouchDistance)
      
      // Only process significant distance changes to avoid jitter
      if (distanceChange > 10 && lastTouchDistance > 0) {
        const scale = currentDistance / lastTouchDistance
        setZoom(prevZoom => {
          const newZoom = prevZoom * scale
          return Math.min(Math.max(newZoom, 0.1), 5)
        })
        setLastTouchDistance(currentDistance)
      }
    }
  }, [touchStart, zoom, pan, setPan, setZoom, getTouchDistance, lastTouchDistance])

  /**
   * Touch end handler - detect swipe gestures for navigation.
   */
  const handleTouchEnd = useCallback((e: React.TouchEvent): void => {
    if (e.changedTouches.length === 1 && e.touches.length === 0) {
      const touch = e.changedTouches[0]
      const deltaX = touch.clientX - touchStart.x
      const deltaY = touch.clientY - touchStart.y
      
      // Check for horizontal swipe when not zoomed
      if (Math.abs(deltaX) > DEFAULT_SWIPE_THRESHOLD && 
          Math.abs(deltaX) > Math.abs(deltaY) * 2 && 
          zoom <= 1) {
        if (deltaX > 0) {
          onPrevImage() // Swipe right - previous image
        } else {
          onNextImage() // Swipe left - next image
        }
      }
    }
    
    // Reset touch states
    setLastTouchDistance(0)
  }, [touchStart, zoom, onPrevImage, onNextImage])

  /**
   * Dynamic container styles based on interaction state.
   */
  const containerStyle = useMemo((): React.CSSProperties => ({
    cursor: zoom > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default',
    touchAction: 'none' // Prevent default touch behaviors
  }), [zoom, isDragging])

  /**
   * Dynamic image transform styles.
   */
  const imageStyle = useMemo((): React.CSSProperties => ({
    transform: `scale(${zoom}) translate(${pan.x / zoom}px, ${pan.y / zoom}px)`,
    transition: isDragging ? 'none' : 'transform 0.2s ease-out'
  }), [zoom, pan, isDragging])

  return {
    isDragging,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    handleWheel,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    containerStyle,
    imageStyle
  }
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Complex Event Typing:
 *    React.MouseEvent, React.TouchEvent, React.WheelEvent with proper generics
 * 
 * 2. Mathematical Calculations:
 *    Distance calculation, pinch scaling, swipe detection
 * 
 * 3. State Machine Pattern:
 *    Different behaviors based on touch count and interaction state
 * 
 * 4. Dynamic Styling:
 *    React.CSSProperties for type-safe dynamic styles
 * 
 * 5. Performance Optimization:
 *    useMemo for expensive style calculations
 * 
 * Benefits of This Hook:
 * - Handles complex multi-touch interactions
 * - Provides smooth pan and zoom experience
 * - Prevents default browser behaviors appropriately
 * - Optimized for performance with memoization
 * - Clear separation of interaction logic
 * - Supports both mouse and touch interfaces
 */