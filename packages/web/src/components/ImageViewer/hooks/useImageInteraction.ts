import { useState, useCallback, useMemo, useRef } from 'react'
import { 
  ImageInteractionHookReturn, 
  PanPosition, 
  DragState, 
  TouchState
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
  
  // Performance optimization: use ref for throttling and debouncing
  const lastUpdateTime = useRef(0)
  const pendingZoomUpdate = useRef<number | null>(null)

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
   * Mouse down handler - start dragging at any zoom level.
   */
  const handleMouseDown = useCallback((e: React.MouseEvent): void => {
    setIsDragging(true)
    setDragStart({
      x: e.clientX - pan.x,
      y: e.clientY - pan.y
    })
  }, [pan])

  /**
   * Mouse move handler - update pan position while dragging.
   */
  const handleMouseMove = useCallback((e: React.MouseEvent): void => {
    if (isDragging) {
      setPan({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y
      })
    }
  }, [isDragging, dragStart, setPan])

  /**
   * Mouse up handler - stop dragging.
   */
  const handleMouseUp = useCallback((): void => {
    setIsDragging(false)
  }, [])

  /**
   * Mouse wheel handler - direct zoom without modifier keys.
   */
  const handleWheel = useCallback((e: React.WheelEvent): void => {
    const delta = e.deltaY > 0 ? 0.965 : 1.035
    setZoom(prev => {
      const newZoom = prev * delta
      // Clamp zoom to valid range
      return Math.min(Math.max(newZoom, 0.1), 5)
    })
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
      // Reset pan state when starting pinch
      if (zoom <= 1) {
        setPan({ x: 0, y: 0 })
      }
    }
  }, [getTouchDistance, zoom, setPan])

  /**
   * Touch move handler - handle pan and pinch gestures.
   */
  const handleTouchMove = useCallback((e: React.TouchEvent): void => {
    if (e.touches.length === 1) {
      // Single touch - pan or swipe detection
      const touch = e.touches[0]
      const deltaX = touch.clientX - touchStart.x
      const deltaY = touch.clientY - touchStart.y
      
      // Allow panning at any zoom level for touch
      setPan(prevPan => ({
        x: prevPan.x + deltaX,
        y: prevPan.y + deltaY
      }))
      setTouchStart({ x: touch.clientX, y: touch.clientY })
    } else if (e.touches.length === 2) {
      // Two fingers - pinch zoom with throttling for performance
      const currentDistance = getTouchDistance(e.touches)
      
      // Process pinch zoom with better performance optimization
      if (lastTouchDistance > 0 && currentDistance > 0) {
        const scale = currentDistance / lastTouchDistance
        const distanceChange = Math.abs(currentDistance - lastTouchDistance)
        
        // Aggressive throttling for high zoom levels to prevent stuttering
        const now = performance.now()
        const timeDiff = now - lastUpdateTime.current
        
        // Adaptive throttling: slower updates for larger zoom levels
        const throttleMs = zoom > 2 ? 66 : zoom > 1.5 ? 50 : 33 // 15fps, 20fps, 30fps
        const shouldUpdate = distanceChange > 10 && timeDiff > throttleMs
        
        if (shouldUpdate) {
          // Clear any pending update
          if (pendingZoomUpdate.current) {
            clearTimeout(pendingZoomUpdate.current)
          }
          
          // Apply conservative smoothing with zoom-based dampening
          const dampening = zoom > 2 ? 0.05 : zoom > 1.5 ? 0.08 : 0.105
          const smoothScale = 1 + (scale - 1) * dampening
          
          setZoom(prevZoom => {
            const newZoom = prevZoom * smoothScale
            return Math.min(Math.max(newZoom, 0.1), 5)
          })
          
          setLastTouchDistance(currentDistance)
          lastUpdateTime.current = now
        }
      } else {
        setLastTouchDistance(currentDistance)
      }
    }
  }, [touchStart, getTouchDistance, setPan, setZoom, lastTouchDistance, zoom])

  /**
   * Touch end handler - detect swipe gestures for navigation.
   */
  const handleTouchEnd = useCallback((e: React.TouchEvent): void => {
    // Disabled swipe navigation to avoid conflicts with drag
    // Users can use navigation arrows or keyboard shortcuts instead
    
    // Reset touch states
    setLastTouchDistance(0)
  }, [])

  /**
   * Dynamic container styles based on interaction state.
   */
  const containerStyle = useMemo((): React.CSSProperties => ({
    cursor: isDragging ? 'grabbing' : 'grab',
    touchAction: 'manipulation' // Allow pinch-zoom and pan but prevent other default behaviors
  }), [isDragging])

  /**
   * Dynamic image transform styles with hardware acceleration and performance optimization.
   */
  const imageStyle = useMemo((): React.CSSProperties => {
    // Round values to reduce precision for better performance
    const roundedZoom = Math.round(zoom * 1000) / 1000
    const roundedPanX = Math.round((pan.x / zoom) * 100) / 100
    const roundedPanY = Math.round((pan.y / zoom) * 100) / 100
    
    return {
      transform: `scale3d(${roundedZoom}, ${roundedZoom}, 1) translate3d(${roundedPanX}px, ${roundedPanY}px, 0)`,
      transition: isDragging ? 'none' : 'transform 0.15s ease-out',
      willChange: isDragging ? 'transform' : 'auto', // Only enable when needed
      backfaceVisibility: 'hidden',
      transformStyle: 'preserve-3d', // Better GPU utilization
      containIntrinsicSize: '100% 100%' // Help browser optimize
    }
  }, [zoom, pan, isDragging])

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