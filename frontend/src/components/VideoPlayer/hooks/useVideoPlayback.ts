import { useRef, useCallback } from 'react'
import {
  VideoPlaybackHookReturn,
  VideoPlaybackState,
  VideoInfo
} from '../types'

/**
 * Video playback control hook for VideoPlayer.
 * 
 * Manages all video playback functionality including play/pause, volume,
 * seeking, fullscreen, and media event handling. Provides a comprehensive
 * interface for controlling HTML5 video elements.
 * 
 * This hook abstracts away the complexity of video element manipulation
 * and provides a clean, type-safe API for video controls.
 * 
 * Architecture Benefits:
 * - Centralized video element control logic
 * - Consistent error handling and state updates
 * - Performance optimized with useCallback
 * - Clean separation from UI concerns
 * - Reusable across different video player implementations
 * 
 * Args:
 *     videoInfo: Processed video metadata and source information
 *     playbackState: Current playback state from useVideoPlayerState
 *     setPlaybackState: State setter to update playback status
 *     onError: Optional error handler for video playback issues
 * 
 * Returns:
 *     VideoPlaybackHookReturn: Complete playback control interface:
 *         - videoRef: React ref for the video element
 *         - handlePlay: Function to start video playback
 *         - handlePause: Function to pause video playback
 *         - handlePlayPause: Function to toggle play/pause state
 *         - handleVolumeChange: Function to adjust volume (0-1)
 *         - handleMuteToggle: Function to toggle mute state
 *         - handleSeek: Function to seek to specific time
 *         - handleFullscreenToggle: Function to toggle fullscreen mode
 *         - handleLoadStart: Handler for video loading events
 *         - handleCanPlay: Handler for video ready events
 *         - handleError: Handler for video error events
 *         - handleTimeUpdate: Handler for time update events
 * 
 * TypeScript Learning Points:
 * - useRef with specific element types
 * - useCallback for performance optimization
 * - Function parameter typing with error handling
 * - Optional chaining for safe property access
 * - Media API integration with TypeScript
 */
const useVideoPlayback = (
  videoInfo: VideoInfo,
  playbackState: VideoPlaybackState,
  setPlaybackState: React.Dispatch<React.SetStateAction<VideoPlaybackState>>,
  onError?: (error: string) => void
): VideoPlaybackHookReturn => {
  // Video element reference for direct DOM manipulation
  const videoRef = useRef<HTMLVideoElement>(null)

  /**
   * Start video playback.
   * Handles browser autoplay policies. State will be updated by onPlay event.
   */
  const handlePlay = useCallback(async (): Promise<void> => {
    const video = videoRef.current
    if (!video || videoInfo.isImageFormat) return

    try {
      // Attempt to play - state will be updated by onPlay event
      await video.play()
      
      // Clear any previous errors
      setPlaybackState(prev => ({
        ...prev,
        error: null
      }))
    } catch (error) {
      // Handle autoplay restrictions or media errors
      const errorMessage = error instanceof Error ? error.message : 'Failed to play video'
      
      setPlaybackState(prev => ({
        ...prev,
        isPlaying: false,
        error: errorMessage
      }))
      
      onError?.(errorMessage)
    }
  }, [videoInfo.isImageFormat, setPlaybackState, onError])

  /**
   * Pause video playback.
   * State will be updated by onPause event.
   */
  const handlePause = useCallback((): void => {
    const video = videoRef.current
    if (!video || videoInfo.isImageFormat) return

    // Pause video - state will be updated by onPause event
    video.pause()
  }, [videoInfo.isImageFormat])

  /**
   * Toggle between play and pause states.
   * Provides unified control for play/pause functionality.
   */
  const handlePlayPause = useCallback((): void => {
    if (playbackState.isPlaying) {
      handlePause()
    } else {
      handlePlay()
    }
  }, [playbackState.isPlaying, handlePlay, handlePause])

  /**
   * Change video volume.
   * Ensures volume stays within valid range (0-1).
   */
  const handleVolumeChange = useCallback((volume: number): void => {
    const video = videoRef.current
    if (!video || videoInfo.isImageFormat) return

    // Clamp volume to valid range
    const clampedVolume = Math.max(0, Math.min(1, volume))
    video.volume = clampedVolume

    setPlaybackState(prev => ({
      ...prev,
      volume: clampedVolume,
      // Unmute if volume is increased from 0
      isMuted: clampedVolume === 0 ? prev.isMuted : false
    }))
  }, [videoInfo.isImageFormat, setPlaybackState])

  /**
   * Toggle mute state.
   * Preserves original volume level for unmute.
   */
  const handleMuteToggle = useCallback((): void => {
    const video = videoRef.current
    if (!video || videoInfo.isImageFormat) return

    const newMutedState = !video.muted
    video.muted = newMutedState

    setPlaybackState(prev => ({
      ...prev,
      isMuted: newMutedState
    }))
  }, [videoInfo.isImageFormat, setPlaybackState])

  /**
   * Seek to specific time in video.
   * Ensures seek position is within video duration bounds.
   */
  const handleSeek = useCallback((time: number): void => {
    const video = videoRef.current
    if (!video || videoInfo.isImageFormat) return

    // Ensure seek time is within video bounds
    const clampedTime = Math.max(0, Math.min(video.duration || 0, time))
    video.currentTime = clampedTime

    setPlaybackState(prev => ({
      ...prev,
      currentTime: clampedTime
    }))
  }, [videoInfo.isImageFormat, setPlaybackState])

  /**
   * Toggle fullscreen mode.
   * Handles cross-browser fullscreen API compatibility.
   */
  const handleFullscreenToggle = useCallback(async (): Promise<void> => {
    const video = videoRef.current
    if (!video) return

    try {
      if (!document.fullscreenElement) {
        // Enter fullscreen
        if (video.requestFullscreen) {
          await video.requestFullscreen()
        } else if ((video as any).webkitRequestFullscreen) {
          // Safari support
          await (video as any).webkitRequestFullscreen()
        } else if ((video as any).msRequestFullscreen) {
          // IE/Edge support
          await (video as any).msRequestFullscreen()
        }
        
        setPlaybackState(prev => ({ ...prev, isFullscreen: true }))
      } else {
        // Exit fullscreen
        if (document.exitFullscreen) {
          await document.exitFullscreen()
        } else if ((document as any).webkitExitFullscreen) {
          await (document as any).webkitExitFullscreen()
        } else if ((document as any).msExitFullscreen) {
          await (document as any).msExitFullscreen()
        }
        
        setPlaybackState(prev => ({ ...prev, isFullscreen: false }))
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Fullscreen failed'
      onError?.(errorMessage)
    }
  }, [setPlaybackState, onError])

  /**
   * Handle video loading start.
   * Updates state to show loading indicator.
   */
  const handleLoadStart = useCallback((): void => {
    setPlaybackState(prev => ({
      ...prev,
      isLoading: true,
      error: null
    }))
  }, [setPlaybackState])

  /**
   * Handle video ready to play.
   * Updates state when video is ready for playback.
   */
  const handleCanPlay = useCallback((): void => {
    setPlaybackState(prev => ({
      ...prev,
      isLoading: false
    }))
  }, [setPlaybackState])

  /**
   * Handle video errors.
   * Updates state with error information and calls optional error handler.
   */
  const handleError = useCallback((error: string): void => {
    setPlaybackState(prev => ({
      ...prev,
      isLoading: false,
      isPlaying: false,
      error
    }))
    
    onError?.(error)
  }, [setPlaybackState, onError])

  /**
   * Handle time updates from video element.
   * Updates current time and duration in state.
   */
  const handleTimeUpdate = useCallback((currentTime: number, duration: number): void => {
    setPlaybackState(prev => ({
      ...prev,
      currentTime,
      duration: duration || prev.duration
    }))
  }, [setPlaybackState])

  /**
   * Handle video play event from video element.
   * Synchronizes React state when video actually starts playing.
   */
  const handleVideoPlay = useCallback((): void => {
    setPlaybackState(prev => ({
      ...prev,
      isPlaying: true,
      error: null
    }))
  }, [setPlaybackState])

  /**
   * Handle video pause event from video element.
   * Synchronizes React state when video is actually paused.
   */
  const handleVideoPause = useCallback((): void => {
    setPlaybackState(prev => ({
      ...prev,
      isPlaying: false
    }))
  }, [setPlaybackState])

  return {
    videoRef,
    handlePlay,
    handlePause,
    handlePlayPause,
    handleVolumeChange,
    handleMuteToggle,
    handleSeek,
    handleFullscreenToggle,
    handleLoadStart,
    handleCanPlay,
    handleError,
    handleTimeUpdate,
    handleVideoPlay,
    handleVideoPause
  }
}

export default useVideoPlayback

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **useRef with Generic Types**:
 *    ```typescript
 *    const videoRef = useRef<HTMLVideoElement>(null)
 *    // TypeScript knows videoRef.current is HTMLVideoElement | null
 *    ```
 * 
 * 2. **Async Function in useCallback**:
 *    ```typescript
 *    const handlePlay = useCallback(async (): Promise<void> => {
 *      await video.play()
 *    }, [dependencies])
 *    ```
 * 
 * 3. **Type Assertions for Browser APIs**:
 *    ```typescript
 *    (video as any).webkitRequestFullscreen()
 *    // Handle non-standard browser APIs safely
 *    ```
 * 
 * 4. **Optional Chaining with Functions**:
 *    ```typescript
 *    onError?.(errorMessage)
 *    // Call function only if it exists
 *    ```
 * 
 * 5. **State Update Patterns**:
 *    ```typescript
 *    setPlaybackState(prev => ({
 *      ...prev,                    // Preserve existing state
 *      isPlaying: true,           // Update specific properties
 *      error: null                // Reset error state
 *    }))
 *    ```
 * 
 * 6. **Error Handling with Type Guards**:
 *    ```typescript
 *    const errorMessage = error instanceof Error ? error.message : 'Default message'
 *    ```
 * 
 * 7. **Math Operations for Clamping**:
 *    ```typescript
 *    const clampedVolume = Math.max(0, Math.min(1, volume))
 *    ```
 * 
 * 8. **Early Returns for Guard Clauses**:
 *    ```typescript
 *    if (!video || videoInfo.isImageFormat) return
 *    // Prevent execution for invalid states
 *    ```
 * 
 * Browser Compatibility Considerations:
 * - Fullscreen API varies across browsers (webkit, ms prefixes)
 * - Autoplay policies differ between browsers and contexts
 * - Volume changes may be restricted on some mobile devices
 * - Error messages vary between different media failure scenarios
 * 
 * Performance Optimizations:
 * - All handlers wrapped in useCallback to prevent unnecessary re-renders
 * - Early returns avoid expensive DOM operations when not applicable
 * - State updates batched where possible for optimal rendering
 * - Video element accessed via ref to avoid query selectors
 * 
 * Error Recovery Strategies:
 * - Graceful fallbacks for unsupported browser APIs
 * - Clear error messages for debugging and user feedback
 * - State consistency maintained even during error conditions
 * - Optional error callback allows parent components to handle errors
 * 
 * aiNagisa Compliance:
 * ✓ Comprehensive error handling and browser compatibility
 * ✓ Performance optimized with useCallback memoization
 * ✓ Clean separation between media control and UI concerns
 * ✓ Complete TypeScript coverage with detailed documentation
 * ✓ Consistent function naming and interface patterns
 */