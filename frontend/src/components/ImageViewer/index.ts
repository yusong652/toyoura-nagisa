/**
 * ImageViewer module exports.
 * 
 * Main export point for the ImageViewer component following
 * aiNagisa's clean architecture standards. Provides both default and
 * named exports for maximum flexibility.
 * 
 * Usage:
 *     // Default import (recommended)
 *     import ImageViewer from './components/ImageViewer'
 *     
 *     // Named import
 *     import { ImageViewer } from './components/ImageViewer'
 *     
 *     // Hook and component imports for advanced usage
 *     import { useImageViewerState, ImageContainer } from './components/ImageViewer'
 * 
 * Architecture:
 * - Main component: ImageViewer.tsx
 * - Custom hooks: ./hooks/
 * - UI components: ./components/
 * - Types: ./types.ts
 * 
 * TypeScript Benefits:
 * - All exports properly typed
 * - Type re-exports for external usage
 * - Clear module boundaries
 * - IDE autocomplete support
 */

// Main component exports
export { default, default as ImageViewer } from './ImageViewer'

// Hook exports for advanced usage
export {
  useImageViewerState,
  useImageNavigation,
  useImageZoom,
  useImageInteraction,
  useThumbnailNavigation
} from './hooks'

// Component exports for custom compositions
export {
  ImageViewerHeader,
  ImageContainer,
  LoadingOverlay,
  ImageControls,
  ImageNavigation,
  ThumbnailStrip
} from './components'

// Type exports for external TypeScript usage
export type {
  // Main component props
  ImageViewerProps,
  
  // Hook return types
  ImageViewerStateHookReturn,
  ImageNavigationHookReturn,
  ImageZoomHookReturn,
  ImageInteractionHookReturn,
  ThumbnailNavigationHookReturn,
  
  // Component prop types
  ImageViewerHeaderProps,
  ImageContainerProps,
  LoadingOverlayProps,
  ImageControlsProps,
  ImageNavigationProps,
  ThumbnailStripProps,
  
  // Utility types
  ImageInfo,
  PanPosition,
  ZoomConstraints
} from './types'

// Constant exports
export { 
  DEFAULT_ZOOM_CONSTRAINTS, 
  DEFAULT_SWIPE_THRESHOLD, 
  ANIMATION_DURATION 
} from './types'