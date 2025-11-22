/**
 * VideoPlayer components module exports.
 * 
 * Centralized export point for all VideoPlayer UI components following
 * aiNagisa's clean architecture standards. Each component handles a specific
 * UI concern within the video player system.
 * 
 * Architecture Benefits:
 * - Modular component design for easy maintenance
 * - Clear separation between different UI sections
 * - Reusable components for different video player layouts
 * - Consistent component patterns across the application
 * 
 * Component Categories:
 * - Layout: Main container and header components
 * - Controls: User interaction elements
 * - Display: Content rendering and loading states
 */

// Header and layout components
export { default as VideoPlayerHeader } from './VideoPlayerHeader'
export { default as VideoContainer } from './VideoContainer'

// Control components
export { default as VideoControls } from './VideoControls'

// Feedback components
export { default as LoadingOverlay } from './LoadingOverlay'

// Re-export types for convenience
export type {
  VideoPlayerHeaderProps,
  VideoContainerProps,
  VideoControlsProps,
  LoadingOverlayProps
} from '../types'