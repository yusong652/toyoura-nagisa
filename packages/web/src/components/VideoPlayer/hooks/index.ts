/**
 * VideoPlayer hooks module exports.
 * 
 * Centralized export point for all VideoPlayer custom hooks following
 * toyoura-nagisa's clean architecture standards. Each hook handles a specific
 * concern within the video player system.
 * 
 * Architecture Benefits:
 * - Clean separation of concerns through focused hooks
 * - Easy testing and maintenance of individual functionalities
 * - Consistent hook patterns across the application
 * - Reusable logic components for other video features
 * 
 * Hook Categories:
 * - State Management: Core video player state
 * - Playback Control: Video playback and media events
 * - Keyboard Shortcuts: User interaction via keyboard
 */

// State management hooks
export { default as useVideoPlayerState } from './useVideoPlayerState'

// Playback control hooks  
export { default as useVideoPlayback } from './useVideoPlayback'

// User interaction hooks
export { default as useVideoKeyboardShortcuts } from './useVideoKeyboardShortcuts'

// Re-export types for convenience
export type {
  VideoPlayerStateHookReturn,
  VideoPlaybackHookReturn, 
  VideoKeyboardShortcutsHookReturn
} from '../types'