/**
 * VideoPlayer module types and interfaces.
 * 
 * Following aiNagisa's clean architecture standards for comprehensive
 * type definitions supporting video playback, format handling, and
 * component interaction.
 * 
 * Architecture Benefits:
 * - Complete TypeScript coverage for all components and hooks
 * - Clear separation between props, state, and utility types
 * - Consistent interface design patterns
 * - Extensible type system for future video features
 * 
 * TypeScript Learning Points:
 * - Interface composition for component hierarchies
 * - Union types for format handling
 * - Generic constraints for type safety
 * - Utility types for state management
 */

import React from 'react'

// =============================================================================
// Core Data Types
// =============================================================================

/**
 * Supported video formats for VideoPlayer.
 * Extensible union type for different video media types.
 */
export type VideoFormat = 'mp4' | 'webm' | 'avi' | 'mov' | 'gif' | 'webp'

/**
 * Video source information with metadata.
 * Used for determining how to render video content.
 */
export interface VideoInfo {
  /** Original video URL or base64 string */
  url: string
  /** Processed video source URL (data URL, blob URL, etc.) */
  source: string
  /** Video format type */
  format: VideoFormat
  /** Whether content should be rendered as image (GIF, static) */
  isImageFormat: boolean
  /** Content duration if available */
  duration?: number
  /** Content dimensions if available */
  dimensions?: {
    width: number
    height: number
  }
}

/**
 * Video playback state for player controls.
 */
export interface VideoPlaybackState {
  /** Whether video is currently playing */
  isPlaying: boolean
  /** Current playback time in seconds */
  currentTime: number
  /** Total video duration in seconds */
  duration: number
  /** Current volume (0-1) */
  volume: number
  /** Whether video is muted */
  isMuted: boolean
  /** Whether video is in fullscreen */
  isFullscreen: boolean
  /** Whether video is loading/buffering */
  isLoading: boolean
  /** Playback error if any */
  error: string | null
}

// =============================================================================
// Main Component Props
// =============================================================================

/**
 * Props for the main VideoPlayer component.
 * 
 * Designed for flexibility while maintaining type safety.
 * Supports various video sources and customization options.
 */
export interface VideoPlayerProps {
  /** Video URL or base64 string to display */
  videoUrl: string
  /** Video format hint (optional, will be auto-detected) */
  format?: VideoFormat
  /** Handler called when player is closed */
  onClose: () => void
  /** Whether to auto-play video on load */
  autoPlay?: boolean
  /** Whether to loop video playback */
  loop?: boolean
  /** Whether to show player controls */
  showControls?: boolean
  /** Initial volume (0-1) */
  initialVolume?: number
  /** Additional CSS classes */
  className?: string
  /** Custom close button text or element */
  closeButtonContent?: React.ReactNode
}

// =============================================================================
// Hook Return Types
// =============================================================================

/**
 * Return type for useVideoPlayerState hook.
 * Manages core video player state and metadata.
 */
export interface VideoPlayerStateHookReturn {
  /** Processed video information */
  videoInfo: VideoInfo
  /** Current playback state */
  playbackState: VideoPlaybackState
  /** Update playback state */
  setPlaybackState: React.Dispatch<React.SetStateAction<VideoPlaybackState>>
  /** Whether player is ready for interaction */
  isReady: boolean
  /** Set player ready state */
  setIsReady: (ready: boolean) => void
}

/**
 * Return type for useVideoPlayback hook.
 * Handles video playback controls and media events.
 */
export interface VideoPlaybackHookReturn {
  /** Video element ref for direct control */
  videoRef: React.RefObject<HTMLVideoElement | null>
  /** Play video */
  handlePlay: () => void
  /** Pause video */
  handlePause: () => void
  /** Toggle play/pause */
  handlePlayPause: () => void
  /** Set video volume (0-1) */
  handleVolumeChange: (volume: number) => void
  /** Toggle mute */
  handleMuteToggle: () => void
  /** Seek to specific time */
  handleSeek: (time: number) => void
  /** Toggle fullscreen mode */
  handleFullscreenToggle: () => void
  /** Handle video loading */
  handleLoadStart: () => void
  /** Handle video ready to play */
  handleCanPlay: () => void
  /** Handle video error */
  handleError: (error: string) => void
  /** Handle time update */
  handleTimeUpdate: (currentTime: number, duration: number) => void
  /** Handle video play event from video element */
  handleVideoPlay: () => void
  /** Handle video pause event from video element */
  handleVideoPause: () => void
}

/**
 * Return type for useVideoKeyboardShortcuts hook.
 * Manages keyboard interactions for video player.
 */
export interface VideoKeyboardShortcutsHookReturn {
  /** Whether shortcuts are currently enabled */
  shortcutsEnabled: boolean
  /** Enable/disable shortcuts */
  setShortcutsEnabled: (enabled: boolean) => void
}

// =============================================================================
// Component Props
// =============================================================================

/**
 * Props for VideoPlayerHeader component.
 * Displays video information and close button.
 */
export interface VideoPlayerHeaderProps {
  /** Video metadata */
  videoInfo: VideoInfo
  /** Close handler */
  onClose: () => void
  /** Custom close button content */
  closeButtonContent?: React.ReactNode
  /** Additional CSS classes */
  className?: string
}

/**
 * Props for VideoContainer component.
 * Main video display area with content rendering.
 */
export interface VideoContainerProps {
  /** Video information and source */
  videoInfo: VideoInfo
  /** Video element ref */
  videoRef?: React.RefObject<HTMLVideoElement | null>
  /** Playback state */
  playbackState: VideoPlaybackState
  /** Auto-play on load */
  autoPlay?: boolean
  /** Loop playback */
  loop?: boolean
  /** Video load start handler */
  onLoadStart?: () => void
  /** Video ready handler */
  onCanPlay?: () => void
  /** Video error handler */
  onError?: (error: string) => void
  /** Time update handler */
  onTimeUpdate?: (currentTime: number, duration: number) => void
  /** Additional CSS classes */
  className?: string
}

/**
 * Props for VideoControls component.
 * Custom video player controls overlay.
 */
export interface VideoControlsProps {
  /** Current playback state */
  playbackState: VideoPlaybackState
  /** Play/pause handler */
  onPlayPause: () => void
  /** Volume change handler */
  onVolumeChange: (volume: number) => void
  /** Mute toggle handler */
  onMuteToggle: () => void
  /** Seek handler */
  onSeek: (time: number) => void
  /** Fullscreen toggle handler */
  onFullscreenToggle: () => void
  /** Whether to show controls */
  visible?: boolean
  /** Additional CSS classes */
  className?: string
}

/**
 * Props for LoadingOverlay component.
 * Displays loading state for video content.
 */
export interface LoadingOverlayProps {
  /** Whether loading is active */
  isLoading: boolean
  /** Loading message */
  message?: string
  /** Additional CSS classes */
  className?: string
}

// =============================================================================
// Constants and Utilities
// =============================================================================

/**
 * Default playback state values.
 * Used for initializing video player state.
 */
export const DEFAULT_PLAYBACK_STATE: VideoPlaybackState = {
  isPlaying: false,
  currentTime: 0,
  duration: 0,
  volume: 1,
  isMuted: false,
  isFullscreen: false,
  isLoading: true,
  error: null
}

/**
 * Video format detection patterns.
 * Used for auto-detecting video formats from URLs.
 */
export const VIDEO_FORMAT_PATTERNS: Record<VideoFormat, RegExp[]> = {
  mp4: [/\.mp4$/i, /video\/mp4/i],
  webm: [/\.webm$/i, /video\/webm/i],
  avi: [/\.avi$/i, /video\/avi/i],
  mov: [/\.mov$/i, /video\/quicktime/i],
  gif: [/\.gif$/i, /image\/gif/i],
  webp: [/\.webp$/i, /image\/webp/i]
}

/**
 * Image-based formats that should be rendered as img elements.
 */
export const IMAGE_FORMATS: VideoFormat[] = ['gif', 'webp']

/**
 * Keyboard shortcuts for video player.
 */
export const KEYBOARD_SHORTCUTS = {
  PLAY_PAUSE: [' ', 'k'],
  VOLUME_UP: ['ArrowUp'],
  VOLUME_DOWN: ['ArrowDown'],
  SEEK_FORWARD: ['ArrowRight'],
  SEEK_BACKWARD: ['ArrowLeft'],
  FULLSCREEN: ['f'],
  MUTE: ['m'],
  ESCAPE: ['Escape']
} as const

/**
 * Default seek increment in seconds.
 */
export const DEFAULT_SEEK_INCREMENT = 10

/**
 * Default volume increment (0-1).
 */
export const DEFAULT_VOLUME_INCREMENT = 0.1

/**
 * Video loading timeout in milliseconds.
 */
export const VIDEO_LOAD_TIMEOUT = 30000

/**
 * Type guard to check if format is image-based.
 * 
 * @param format - Video format to check
 * @returns Whether format should be rendered as image
 */
export const isImageFormat = (format: VideoFormat): boolean => {
  return IMAGE_FORMATS.includes(format)
}

/**
 * Utility to detect video format from URL.
 * 
 * @param url - Video URL to analyze
 * @returns Detected format or 'mp4' as default
 */
export const detectVideoFormat = (url: string): VideoFormat => {
  for (const [format, patterns] of Object.entries(VIDEO_FORMAT_PATTERNS)) {
    if (patterns.some(pattern => pattern.test(url))) {
      return format as VideoFormat
    }
  }
  return 'mp4' // Default fallback
}

/**
 * Utility to normalize video URL to proper data URL format.
 * 
 * @param url - Raw video URL or base64 string
 * @param format - Video format hint
 * @returns Properly formatted data URL or original URL
 */
export const normalizeVideoUrl = (url: string, format: VideoFormat): string => {
  // Already a data URL or blob URL
  if (url.startsWith('data:') || url.startsWith('blob:')) {
    return url
  }
  
  // Contains base64 but not properly formatted
  if (url.includes('base64')) {
    const mimeType = isImageFormat(format) ? `image/${format}` : `video/${format}`
    return `data:${mimeType};base64,${url}`
  }
  
  // Regular URL
  return url
}

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Interface Composition**:
 *    Building complex interfaces from simpler ones using extends
 * 
 * 2. **Union Types**: 
 *    VideoFormat type allows only specific string values
 * 
 * 3. **Generic Constraints**:
 *    React.RefObject<HTMLVideoElement> ensures proper element typing
 * 
 * 4. **Utility Types**:
 *    React.Dispatch<React.SetStateAction<T>> for state setters
 * 
 * 5. **Constant Assertions**:
 *    'as const' makes KEYBOARD_SHORTCUTS deeply readonly
 * 
 * 6. **Type Guards**:
 *    isImageFormat function provides runtime type checking
 * 
 * 7. **Mapped Types**:
 *    Record<VideoFormat, RegExp[]> creates format-to-pattern mapping
 * 
 * 8. **Optional Properties**:
 *    Strategic use of ? for flexible component APIs
 * 
 * 9. **Function Typing**:
 *    Complete event handler signatures for type safety
 * 
 * 10. **Namespace Organization**:
 *     Logical grouping of related types and utilities
 * 
 * Architecture Benefits:
 * - Single source of truth for all VideoPlayer types
 * - Clear separation between data, state, and component types
 * - Extensible design for future video features
 * - Comprehensive utility functions with proper typing
 * - Consistent interface patterns across the module
 * 
 * aiNagisa Compliance:
 * ✓ Detailed TypeScript documentation
 * ✓ Logical type organization and grouping
 * ✓ Utility functions with type guards
 * ✓ Complete component prop definitions
 * ✓ Hook return type interfaces
 * ✓ Constants with proper typing
 */