import { useCallback, useMemo } from 'react'
import { 
  ImageZoomHookReturn, 
  PanPosition, 
  DEFAULT_ZOOM_CONSTRAINTS 
} from '../types'

/**
 * Custom hook for managing image zoom functionality.
 * 
 * Handles zoom in/out/reset operations with proper constraints and
 * pan position management. Ensures zoom levels stay within bounds
 * and resets pan when appropriate.
 * 
 * Args:
 *     zoom: Current zoom level
 *     setZoom: Function to update zoom level
 *     setPan: Function to update pan position
 * 
 * Returns:
 *     ImageZoomHookReturn: Zoom functions and state:
 *         - handleZoomIn: Increase zoom level
 *         - handleZoomOut: Decrease zoom level  
 *         - handleZoomReset: Reset to 100% zoom
 *         - canZoomIn: Whether zoom in is possible
 *         - canZoomOut: Whether zoom out is possible
 * 
 * TypeScript Learning Points:
 * - Hook composition with state setters as parameters
 * - Mathematical constraints with bounds checking
 * - Side effect management (pan reset on zoom reset)
 * - Boolean derived state with useMemo
 */
export const useImageZoom = (
  zoom: number,
  setZoom: (zoom: number | ((prev: number) => number)) => void,
  setPan: (pan: PanPosition | ((prev: PanPosition) => PanPosition)) => void
): ImageZoomHookReturn => {
  /**
   * Zoom in by the configured step amount.
   * Automatically clamps to maximum zoom level.
   */
  const handleZoomIn = useCallback((): void => {
    setZoom(prev => Math.min(prev * DEFAULT_ZOOM_CONSTRAINTS.step, DEFAULT_ZOOM_CONSTRAINTS.max))
  }, [setZoom])

  /**
   * Zoom out by the configured step amount.
   * Automatically clamps to minimum zoom level.
   */
  const handleZoomOut = useCallback((): void => {
    setZoom(prev => Math.max(prev / DEFAULT_ZOOM_CONSTRAINTS.step, DEFAULT_ZOOM_CONSTRAINTS.min))
  }, [setZoom])

  /**
   * Reset zoom to 100% and center the image.
   * Clears any pan offset to return image to center.
   */
  const handleZoomReset = useCallback((): void => {
    setZoom(1)
    setPan({ x: 0, y: 0 })
  }, [setZoom, setPan])

  /**
   * Determine if zoom in is possible.
   * Checks against maximum zoom constraint.
   */
  const canZoomIn = useMemo((): boolean => {
    return zoom < DEFAULT_ZOOM_CONSTRAINTS.max
  }, [zoom])

  /**
   * Determine if zoom out is possible.
   * Checks against minimum zoom constraint.
   */
  const canZoomOut = useMemo((): boolean => {
    return zoom > DEFAULT_ZOOM_CONSTRAINTS.min
  }, [zoom])

  return {
    handleZoomIn,
    handleZoomOut,
    handleZoomReset,
    canZoomIn,
    canZoomOut
  }
}

/**
 * Extended zoom hook with custom constraints:
 * 
 * export const useImageZoomAdvanced = (
 *   zoom: number,
 *   setZoom: (zoom: number) => void,
 *   setPan: (pan: PanPosition) => void,
 *   constraints: ZoomConstraints = DEFAULT_ZOOM_CONSTRAINTS
 * ) => {
 *   const handleZoomToLevel = useCallback((level: number): void => {
 *     const clampedLevel = Math.min(Math.max(level, constraints.min), constraints.max)
 *     setZoom(clampedLevel)
 *     
 *     // Reset pan if zooming out to fit
 *     if (clampedLevel <= 1) {
 *       setPan({ x: 0, y: 0 })
 *     }
 *   }, [setZoom, setPan, constraints])
 * 
 *   const handleZoomToFit = useCallback((): void => {
 *     handleZoomToLevel(1)
 *   }, [handleZoomToLevel])
 * 
 *   return {
 *     ...baseHook,
 *     handleZoomToLevel,
 *     handleZoomToFit
 *   }
 * }
 */

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Hook Composition:
 *    Takes setter functions as parameters for state coupling
 * 
 * 2. Mathematical Operations:
 *    Zoom calculations with proper bounds checking
 * 
 * 3. Side Effect Coordination:
 *    handleZoomReset affects both zoom and pan state
 * 
 * 4. Constraint Validation:
 *    canZoom* booleans derived from current state vs limits
 * 
 * 5. Function Memoization:
 *    useCallback ensures stable function references
 * 
 * Benefits of This Hook:
 * - Encapsulates all zoom-related logic
 * - Automatic bounds checking prevents invalid states
 * - Coordinates between zoom and pan for better UX
 * - Performance optimized with memoization
 * - Easy to extend with additional zoom features
 * - Clear API with descriptive function names
 * - Testable zoom logic in isolation
 */