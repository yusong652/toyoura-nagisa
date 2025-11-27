/**
 * VideoPlayer module exports.
 * 
 * Main export point for the VideoPlayer component following
 * aiNagisa's clean architecture standards. Provides both default and
 * named exports for maximum flexibility.
 * 
 * Usage:
 *     // Default import (recommended)
 *     import VideoPlayer from './components/VideoPlayer'
 *     
 *     // Named import
 *     import { VideoPlayer } from './components/VideoPlayer'
 *     
 *     // Hook and component imports for advanced usage
 *     import { useVideoPlayerState, VideoContainer } from './components/VideoPlayer'
 * 
 * Architecture:
 * - Main component: VideoPlayer.tsx
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
export { default, default as VideoPlayer } from './VideoPlayer'

// Hook exports for advanced usage
export {
  useVideoPlayerState,
  useVideoPlayback,
  useVideoKeyboardShortcuts
} from './hooks'

// Component exports for custom compositions
export {
  VideoPlayerHeader,
  VideoContainer,
  VideoControls,
  LoadingOverlay
} from './components'

// Type exports for external TypeScript usage
export type {
  // Main component props
  VideoPlayerProps,
  
  // Hook return types
  VideoPlayerStateHookReturn,
  VideoPlaybackHookReturn,
  VideoKeyboardShortcutsHookReturn,
  
  // Component prop types
  VideoPlayerHeaderProps,
  VideoContainerProps,
  VideoControlsProps,
  LoadingOverlayProps,
  
  // Data types
  VideoInfo,
  VideoPlaybackState,
  VideoFormat
} from './types'

// Constant exports
export {
  DEFAULT_PLAYBACK_STATE,
  VIDEO_FORMAT_PATTERNS,
  IMAGE_FORMATS,
  KEYBOARD_SHORTCUTS,
  DEFAULT_SEEK_INCREMENT,
  DEFAULT_VOLUME_INCREMENT,
  VIDEO_LOAD_TIMEOUT,
  isImageFormat,
  detectVideoFormat,
  normalizeVideoUrl
} from './types'