import React from 'react'
import { VideoPlayerHeaderProps } from '../types'

/**
 * VideoPlayer header component with video info and close button.
 * 
 * Displays video metadata and provides a prominent close button following
 * toyoura-nagisa's component composition patterns. Designed to work consistently
 * with other modal header components in the application.
 * 
 * Features:
 * - Video format and source information display
 * - Prominent close button with proper accessibility
 * - Responsive design for different screen sizes
 * - Consistent styling with other modal headers
 * 
 * Architecture Benefits:
 * - Single responsibility (header display only)
 * - Reusable across different video player layouts
 * - Clean props interface for easy customization
 * - Consistent with toyoura-nagisa header patterns
 * 
 * Args:
 *     videoInfo: Processed video metadata including format and source
 *     onClose: Handler called when close button is clicked
 *     closeButtonContent: Optional custom close button content
 *     className: Additional CSS classes for styling customization
 * 
 * Returns:
 *     JSX.Element: Complete header with video info and close button
 * 
 * TypeScript Learning Points:
 * - Interface-based props with optional customization
 * - React.ReactNode for flexible content types
 * - Conditional rendering with logical operators
 * - Event handler typing for button interactions
 * - CSS class composition patterns
 */
const VideoPlayerHeader: React.FC<VideoPlayerHeaderProps> = ({
  videoInfo,
  onClose,
  closeButtonContent = '×',
  className = ''
}) => {
  return (
    <div className={`video-player-header ${className}`.trim()}>
      {/* Video information section */}
      <div className="video-info">
        <div className="video-title">
          {videoInfo.format.toUpperCase()} Content
        </div>
        
        {videoInfo.dimensions && (
          <div className="video-details">
            {videoInfo.dimensions.width}x{videoInfo.dimensions.height}
          </div>
        )}
        
        {videoInfo.duration && (
          <div className="video-duration">
            {formatDuration(videoInfo.duration)}
          </div>
        )}
      </div>

      {/* Close button with accessibility features */}
      <button
        className="video-close-button"
        onClick={onClose}
        aria-label="Close video player"
        type="button"
        title="Close (Esc)"
      >
        {closeButtonContent}
      </button>
    </div>
  )
}

/**
 * Utility function to format video duration.
 * Converts seconds to human-readable MM:SS or HH:MM:SS format.
 * 
 * @param seconds - Duration in seconds
 * @returns Formatted duration string
 */
const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
  } else {
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`
  }
}

export default VideoPlayerHeader

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Component Props Interface**:
 *    ```typescript
 *    interface VideoPlayerHeaderProps {
 *      videoInfo: VideoInfo
 *      onClose: () => void
 *      closeButtonContent?: React.ReactNode
 *    }
 *    ```
 * 
 * 2. **Default Parameters**:
 *    ```typescript
 *    const Component = ({ 
 *      closeButtonContent = '×',  // Default value
 *      className = '' 
 *    }: Props) => { }
 *    ```
 * 
 * 3. **Conditional Rendering**:
 *    ```typescript
 *    {videoInfo.dimensions && (
 *      <div>{videoInfo.dimensions.width}x{videoInfo.dimensions.height}</div>
 *    )}
 *    ```
 * 
 * 4. **String Template Literals**:
 *    ```typescript
 *    className={`video-player-header ${className}`.trim()}
 *    ```
 * 
 * 5. **Utility Function Integration**:
 *    ```typescript
 *    const formatDuration = (seconds: number): string => {
 *      // Format logic
 *    }
 *    ```
 * 
 * 6. **Math Operations for Time**:
 *    ```typescript
 *    const hours = Math.floor(seconds / 3600)
 *    const minutes = Math.floor((seconds % 3600) / 60)
 *    ```
 * 
 * 7. **String Padding**:
 *    ```typescript
 *    minutes.toString().padStart(2, '0')  // '05' from 5
 *    ```
 * 
 * 8. **Accessibility Attributes**:
 *    ```typescript
 *    <button 
 *      aria-label="Close video player"
 *      title="Close (Esc)"
 *    >
 *    ```
 * 
 * Component Design Patterns:
 * - Single responsibility (header display only)
 * - Props-based customization for flexibility
 * - Accessibility-first design with proper ARIA labels
 * - Consistent styling approach with CSS classes
 * 
 * CSS Classes Expected:
 * - .video-player-header: Main header container
 * - .video-info: Video metadata section
 * - .video-title: Format display styling
 * - .video-details: Dimensions display
 * - .video-duration: Duration display
 * - .video-close-button: Close button styling
 * 
 * Accessibility Features:
 * - aria-label for screen reader context
 * - title attribute for tooltip information
 * - button type for proper keyboard navigation
 * - Semantic HTML structure for screen readers
 * 
 * User Experience Enhancements:
 * - Clear video format identification
 * - Duration display for user orientation
 * - Prominent close button for easy exit
 * - Responsive design considerations
 * 
 * Integration Benefits:
 * - Works with VideoInfo from useVideoPlayerState
 * - Consistent with other modal header components
 * - Easy to customize with props and CSS classes
 * - Supports different close button styles
 * 
 * toyoura-nagisa Compliance:
 * ✓ Single responsibility principle
 * ✓ Props-based interface design  
 * ✓ Accessibility and user experience focus
 * ✓ Clear TypeScript typing and documentation
 * ✓ Consistent component patterns and naming
 */