import React from 'react'
import { VideoContainerProps } from '../types'
import LoadingOverlay from './LoadingOverlay'

/**
 * VideoContainer component for main video content display.
 * 
 * Central container that handles video rendering, loading states, and
 * event handling. Supports both video elements and image formats (GIFs)
 * with proper fallback handling and accessibility features.
 * 
 * This component serves as the main content area, coordinating between
 * video playback and loading/error states while maintaining clean
 * separation of concerns.
 * 
 * Architecture Benefits:
 * - Handles both video and image content seamlessly
 * - Clean event handler integration
 * - Loading and error state management
 * - Accessibility features built-in
 * - Consistent with other media container components
 * 
 * Args:
 *     videoInfo: Processed video metadata and source information
 *     videoRef: Optional ref for video element (for playback controls)
 *     playbackState: Current playback status including loading state
 *     autoPlay: Whether to auto-play video on load
 *     loop: Whether to loop video playback
 *     showControls: Whether to show native video controls
 *     onLoadStart: Handler for video loading start events
 *     onCanPlay: Handler for video ready events
 *     onError: Handler for video error events
 *     onTimeUpdate: Handler for time update events
 *     className: Additional CSS classes for styling
 * 
 * Returns:
 *     JSX.Element: Complete video container with content and loading states
 * 
 * TypeScript Learning Points:
 * - Conditional rendering based on content type
 * - Event handler prop threading
 * - Optional ref handling with proper typing
 * - Component composition with loading overlays
 * - Media element event handling
 */
const VideoContainer: React.FC<VideoContainerProps> = ({
  videoInfo,
  videoRef,
  playbackState,
  autoPlay = false,
  loop = false,
  showControls = true,
  onLoadStart,
  onCanPlay,
  onError,
  onTimeUpdate,
  className = ''
}) => {
  /**
   * Handle video element error events.
   * Converts media error to user-friendly message.
   */
  const handleVideoError = (e: React.SyntheticEvent<HTMLVideoElement, Event>): void => {
    const video = e.currentTarget
    const error = video.error
    
    let errorMessage = 'Failed to load video'
    
    if (error) {
      switch (error.code) {
        case MediaError.MEDIA_ERR_ABORTED:
          errorMessage = 'Video loading was aborted'
          break
        case MediaError.MEDIA_ERR_NETWORK:
          errorMessage = 'Network error occurred while loading video'
          break
        case MediaError.MEDIA_ERR_DECODE:
          errorMessage = 'Video format is not supported'
          break
        case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
          errorMessage = 'Video source is not supported'
          break
        default:
          errorMessage = 'Unknown video error occurred'
      }
    }
    
    onError?.(errorMessage)
  }

  /**
   * Handle video time updates.
   * Extracts current time and duration from video element.
   */
  const handleTimeUpdate = (e: React.SyntheticEvent<HTMLVideoElement, Event>): void => {
    const video = e.currentTarget
    onTimeUpdate?.(video.currentTime, video.duration || 0)
  }

  /**
   * Handle video loading start.
   * Notifies parent components that loading has begun.
   */
  const handleLoadStart = (): void => {
    onLoadStart?.()
  }

  /**
   * Handle video ready to play.
   * Notifies parent components that video can start playback.
   */
  const handleCanPlay = (): void => {
    onCanPlay?.()
  }

  /**
   * Handle image loading errors for GIF/image formats.
   * Provides fallback error handling for image-based content.
   */
  const handleImageError = (): void => {
    onError?.('Failed to load image content')
  }

  return (
    <div className={`video-container ${className}`.trim()}>
      {/* Loading overlay - shown when content is loading */}
      {playbackState.isLoading && (
        <LoadingOverlay 
          isLoading={true}
          message="Loading content..."
          className="video-loading-overlay"
        />
      )}

      {/* Content rendering based on format type */}
      {videoInfo.isImageFormat ? (
        // Render as image for GIFs and static images
        <img
          src={videoInfo.source}
          alt="Video content"
          className="video-content video-gif"
          draggable={false}
          onError={handleImageError}
        />
      ) : (
        // Render as video element for video formats
        <video
          ref={videoRef}
          src={videoInfo.source}
          className="video-content video-element"
          autoPlay={autoPlay}
          loop={loop}
          controls={showControls}
          playsInline
          preload="metadata"
          // Event handlers
          onLoadStart={handleLoadStart}
          onCanPlay={handleCanPlay}
          onError={handleVideoError}
          onTimeUpdate={handleTimeUpdate}
          // Prevent context menu for better UX
          onContextMenu={(e) => e.preventDefault()}
        >
          {/* Fallback content for unsupported browsers */}
          Your browser does not support the video tag.
        </video>
      )}

      {/* Error state display */}
      {playbackState.error && !playbackState.isLoading && (
        <div className="video-error">
          <div className="error-message">
            {playbackState.error}
          </div>
          <div className="error-details">
            Please try refreshing or contact support if the problem persists.
          </div>
        </div>
      )}
    </div>
  )
}

export default VideoContainer

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Event Handler Typing**:
 *    ```typescript
 *    const handleVideoError = (e: React.SyntheticEvent<HTMLVideoElement, Event>): void => {
 *      const video = e.currentTarget  // TypeScript knows this is HTMLVideoElement
 *    }
 *    ```
 * 
 * 2. **Media API Error Handling**:
 *    ```typescript
 *    const error = video.error
 *    if (error) {
 *      switch (error.code) {
 *        case MediaError.MEDIA_ERR_ABORTED:
 *          // Handle specific error types
 *      }
 *    }
 *    ```
 * 
 * 3. **Optional Chaining with Functions**:
 *    ```typescript
 *    onError?.(errorMessage)
 *    // Call function only if it exists
 *    ```
 * 
 * 4. **Conditional Rendering Patterns**:
 *    ```typescript
 *    {videoInfo.isImageFormat ? (
 *      <img src={videoInfo.source} />
 *    ) : (
 *      <video src={videoInfo.source} />
 *    )}
 *    ```
 * 
 * 5. **Ref Prop Threading**:
 *    ```typescript
 *    <video ref={videoRef} />
 *    // videoRef is React.RefObject<HTMLVideoElement> | undefined
 *    ```
 * 
 * 6. **Component Composition**:
 *    ```typescript
 *    <LoadingOverlay 
 *      isLoading={true}
 *      className="video-loading-overlay"
 *    />
 *    ```
 * 
 * 7. **Event Handler Prop Threading**:
 *    Passing event handlers from parent components to DOM elements
 * 
 * 8. **CSS Class Composition**:
 *    ```typescript
 *    className={`video-container ${className}`.trim()}
 *    ```
 * 
 * Error Handling Strategy:
 * - Specific error messages for different media error types
 * - Graceful fallback for unsupported content
 * - Clear user feedback for error conditions
 * - Separate error handling for images vs videos
 * 
 * Accessibility Features:
 * - Alt text for image content
 * - Semantic HTML structure
 * - Screen reader friendly error messages
 * - Keyboard navigation support through video controls
 * 
 * Performance Considerations:
 * - preload="metadata" for faster initial loading
 * - playsInline for mobile optimization
 * - Conditional rendering to avoid unnecessary DOM elements
 * - Event handler optimization with optional chaining
 * 
 * User Experience Enhancements:
 * - Loading state feedback with overlay
 * - Context menu disabled to prevent download prompts
 * - Error state with helpful recovery instructions
 * - Consistent styling between image and video content
 * 
 * Browser Compatibility:
 * - Fallback content for unsupported browsers
 * - Standard HTML5 video attributes
 * - Cross-browser error handling
 * - Mobile-optimized playback settings
 * 
 * CSS Classes Expected:
 * - .video-container: Main container styling
 * - .video-content: Common content styling
 * - .video-element: Video-specific styling
 * - .video-gif: Image-specific styling
 * - .video-loading-overlay: Loading state styling
 * - .video-error: Error state container
 * - .error-message: Error message styling
 * - .error-details: Error details styling
 * 
 * aiNagisa Compliance:
 * ✓ Clean separation between content types (video vs image)
 * ✓ Comprehensive error handling and user feedback
 * ✓ Accessibility features and semantic HTML
 * ✓ Performance optimized loading and rendering
 * ✓ Consistent component composition patterns
 */