import { useState, useEffect, useMemo } from 'react'
import {
  VideoPlayerStateHookReturn,
  VideoInfo,
  VideoPlaybackState,
  VideoFormat,
  DEFAULT_PLAYBACK_STATE,
  detectVideoFormat,
  normalizeVideoUrl,
  isImageFormat
} from '../types'

/**
 * Core state management hook for VideoPlayer.
 * 
 * Manages video metadata, playback state, and player readiness following
 * aiNagisa's separation of concerns principle. Handles format detection,
 * URL normalization, and state initialization.
 * 
 * This hook serves as the central state coordinator, providing processed
 * video information and playback state to other components and hooks.
 * 
 * Architecture Benefits:
 * - Single source of truth for video player state
 * - Automatic format detection and URL processing
 * - Clean separation between data processing and UI logic
 * - Optimized with memoization for performance
 * 
 * Args:
 *     videoUrl: Raw video URL or base64 string
 *     format: Optional format hint for video type
 *     autoPlay: Whether to auto-play when ready
 * 
 * Returns:
 *     VideoPlayerStateHookReturn: Complete state management interface:
 *         - videoInfo: Processed video metadata and source URL
 *         - playbackState: Current playback status and controls state
 *         - setPlaybackState: State setter for playback updates
 *         - isReady: Whether player is ready for user interaction
 *         - setIsReady: Function to update player ready state
 * 
 * TypeScript Learning Points:
 * - useMemo for expensive computations with dependency arrays
 * - useState with complex object state types
 * - Type inference from custom type definitions
 * - Utility function integration within hooks
 * - State initialization with default values
 */
const useVideoPlayerState = (
  videoUrl: string,
  format?: VideoFormat,
  autoPlay?: boolean
): VideoPlayerStateHookReturn => {
  // Memoized video information processing
  // Recalculates only when videoUrl or format changes
  const videoInfo: VideoInfo = useMemo(() => {
    // Auto-detect format if not provided
    const detectedFormat = format || detectVideoFormat(videoUrl)
    
    // Normalize URL to proper data URL format
    const processedSource = normalizeVideoUrl(videoUrl, detectedFormat)
    
    return {
      url: videoUrl,
      source: processedSource,
      format: detectedFormat,
      isImageFormat: isImageFormat(detectedFormat),
      // Additional metadata could be extracted here
      duration: undefined,
      dimensions: undefined
    }
  }, [videoUrl, format])

  // Playback state management
  // Initialize with default values, considering autoPlay preference
  const [playbackState, setPlaybackState] = useState<VideoPlaybackState>(() => ({
    ...DEFAULT_PLAYBACK_STATE,
    // If autoPlay is requested, start with playing intent
    // Actual playback depends on browser policies and user interaction
    isPlaying: autoPlay || false
  }))

  // Player readiness state
  // Tracks whether player is initialized and ready for interaction
  const [isReady, setIsReady] = useState<boolean>(false)

  // Reset states when video URL changes
  useEffect(() => {
    // Reset playback state to defaults
    setPlaybackState(prev => ({
      ...DEFAULT_PLAYBACK_STATE,
      // Preserve autoPlay intent for new video
      isPlaying: autoPlay || false
    }))
    
    // Reset readiness state
    setIsReady(false)
  }, [videoUrl, autoPlay])

  return {
    videoInfo,
    playbackState,
    setPlaybackState,
    isReady,
    setIsReady
  }
}

export default useVideoPlayerState

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Custom Hook Pattern**:
 *    Function that uses React hooks and returns an object interface
 * 
 * 2. **useMemo Optimization**:
 *    ```typescript
 *    const videoInfo = useMemo(() => {
 *      return computeVideoInfo()
 *    }, [videoUrl, format])  // Only recompute when dependencies change
 *    ```
 * 
 * 3. **State Initialization Function**:
 *    ```typescript
 *    const [state, setState] = useState<Type>(() => ({
 *      // Compute initial state
 *    }))
 *    ```
 * 
 * 4. **Spread Operator with Object Updates**:
 *    ```typescript
 *    setPlaybackState(prev => ({
 *      ...DEFAULT_PLAYBACK_STATE,  // Base values
 *      isPlaying: autoPlay || false  // Override specific properties
 *    }))
 *    ```
 * 
 * 5. **Optional Parameter Handling**:
 *    Using || operator for default values when parameters are optional
 * 
 * 6. **Type Import Organization**:
 *    Importing specific types and utilities from the types module
 * 
 * 7. **Effect Dependency Management**:
 *    useEffect dependencies array determines when side effects run
 * 
 * 8. **Complex State Objects**:
 *    Managing state objects with multiple properties and proper typing
 * 
 * Performance Considerations:
 * - videoInfo memoization prevents unnecessary recalculations
 * - State updates are batched by React for optimal rendering
 * - URL normalization happens only when inputs change
 * - Format detection runs once per video URL change
 * 
 * Hook Composition Benefits:
 * - Other hooks can consume this state through the return interface
 * - State changes trigger re-renders only where needed
 * - Clean separation between data processing and presentation logic
 * - Easy to test state logic independently of UI components
 * 
 * Error Handling Strategy:
 * - Format detection falls back to 'mp4' for unknown formats
 * - URL normalization handles various input formats gracefully
 * - State initialization provides safe defaults for all scenarios
 * 
 * aiNagisa Compliance:
 * ✓ Single responsibility (state management only)
 * ✓ Optimized performance with memoization
 * ✓ Clear TypeScript interfaces and documentation
 * ✓ Consistent hook patterns and naming
 * ✓ Separation of concerns from UI logic
 */