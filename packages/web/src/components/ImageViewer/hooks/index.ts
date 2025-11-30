/**
 * ImageViewer hooks module exports.
 * 
 * Centralized exports for all image viewer related custom hooks.
 * Following toyoura-nagisa's clean architecture pattern with organized hook modules.
 * 
 * Usage:
 *     import { useImageViewerState, useImageNavigation } from './hooks'
 * 
 * Architecture:
 *     - useImageViewerState: Core state management (index, zoom, pan, loading)
 *     - useImageNavigation: Image navigation logic (prev/next with circular support)
 *     - useImageZoom: Zoom functionality with constraints
 *     - useImageInteraction: Mouse and touch interaction handling
 *     - useThumbnailNavigation: Thumbnail strip auto-scrolling
 * 
 * TypeScript Benefits:
 * - Single import point for all hooks
 * - Type re-exports for convenience  
 * - Clear module boundaries
 * - IDE autocomplete support
 */

export { useImageViewerState } from './useImageViewerState'
export { useImageNavigation } from './useImageNavigation'
export { useImageZoom } from './useImageZoom'
export { useImageInteraction } from './useImageInteraction'
export { useThumbnailNavigation } from './useThumbnailNavigation'

// Re-export hook return types for convenience
export type {
  ImageViewerStateHookReturn,
  ImageNavigationHookReturn,
  ImageZoomHookReturn,
  ImageInteractionHookReturn,
  ThumbnailNavigationHookReturn
} from '../types'