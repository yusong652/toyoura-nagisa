/**
 * ImageViewer components module exports.
 * 
 * Centralized exports for all image viewer UI components.
 * Following aiNagisa's modular component architecture pattern.
 * 
 * Usage:
 *     import { ImageViewerHeader, ImageContainer } from './components'
 * 
 * Architecture:
 *     - ImageViewerHeader: Header with image info and close button
 *     - ImageContainer: Main image display with interactions
 *     - LoadingOverlay: Loading state with spinner
 *     - ImageControls: Zoom control buttons
 *     - ImageNavigation: Previous/next navigation arrows
 *     - ThumbnailStrip: Scrollable thumbnail navigation
 * 
 * Component Responsibilities:
 * - Each component handles a single UI concern
 * - Props are strongly typed with TypeScript interfaces
 * - Accessibility features are built into each component
 * - Clean separation between display and interaction logic
 */

export { default as ImageViewerHeader } from './ImageViewerHeader'
export { default as ImageContainer } from './ImageContainer'
export { default as LoadingOverlay } from './LoadingOverlay'
export { default as ImageControls } from './ImageControls'
export { default as ImageNavigation } from './ImageNavigation'
export { default as ThumbnailStrip } from './ThumbnailStrip'

// Re-export component prop types for convenience
export type { 
  ImageViewerHeaderProps,
  ImageContainerProps,
  LoadingOverlayProps,
  ImageControlsProps,
  ImageNavigationProps,
  ThumbnailStripProps
} from '../types'