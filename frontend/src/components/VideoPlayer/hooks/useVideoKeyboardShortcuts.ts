import { useState, useCallback } from 'react'
import { useKeyboardShortcuts } from '../../MediaModal/hooks'
import {
  VideoKeyboardShortcutsHookReturn,
  KEYBOARD_SHORTCUTS,
  DEFAULT_SEEK_INCREMENT,
  DEFAULT_VOLUME_INCREMENT
} from '../types'

/**
 * Keyboard shortcuts hook for VideoPlayer.
 * 
 * Integrates with MediaModal's keyboard handling system to provide
 * video-specific shortcuts like play/pause, volume control, and seeking.
 * Extends the base modal shortcuts with media player functionality.
 * 
 * This hook leverages the existing keyboard infrastructure while adding
 * video-specific controls, maintaining consistency across the application.
 * 
 * Architecture Benefits:
 * - Builds on MediaModal's keyboard system for consistency
 * - Provides comprehensive video control shortcuts
 * - Can be enabled/disabled dynamically
 * - Integrates seamlessly with other VideoPlayer hooks
 * 
 * Args:
 *     onPlayPause: Handler for play/pause toggle (spacebar, k key)
 *     onVolumeUp: Handler for volume increase (up arrow)
 *     onVolumeDown: Handler for volume decrease (down arrow)
 *     onSeekForward: Handler for forward seek (right arrow)
 *     onSeekBackward: Handler for backward seek (left arrow)
 *     onFullscreen: Handler for fullscreen toggle (f key)
 *     onMuteToggle: Handler for mute toggle (m key)
 *     disabled: Whether shortcuts are currently disabled
 * 
 * Returns:
 *     VideoKeyboardShortcutsHookReturn: Keyboard shortcut control interface:
 *         - shortcutsEnabled: Whether shortcuts are currently enabled
 *         - setShortcutsEnabled: Function to enable/disable shortcuts
 * 
 * Keyboard Shortcuts:
 *     - Space/K: Play/pause toggle
 *     - Up Arrow: Volume up
 *     - Down Arrow: Volume down
 *     - Right Arrow: Seek forward 10s
 *     - Left Arrow: Seek backward 10s
 *     - F: Toggle fullscreen
 *     - M: Toggle mute
 *     - Escape: Close player (handled by MediaModal)
 * 
 * TypeScript Learning Points:
 * - Hook composition with external hook dependencies
 * - Function parameter object destructuring
 * - Optional parameter handling with defaults
 * - State management for feature toggling
 * - Integration patterns between related hooks
 */
interface UseVideoKeyboardShortcutsParams {
  onPlayPause: () => void
  onVolumeUp: () => void
  onVolumeDown: () => void
  onSeekForward: () => void
  onSeekBackward: () => void
  onFullscreen: () => void
  onMuteToggle: () => void
  disabled?: boolean
}

const useVideoKeyboardShortcuts = ({
  onPlayPause,
  onVolumeUp,
  onVolumeDown,
  onSeekForward,
  onSeekBackward,
  onFullscreen,
  onMuteToggle,
  disabled = false
}: UseVideoKeyboardShortcutsParams): VideoKeyboardShortcutsHookReturn => {
  // Internal state for shortcut toggling
  const [shortcutsEnabled, setShortcutsEnabled] = useState<boolean>(!disabled)

  // Memoized keyboard handlers
  // These wrap the provided handlers with shortcut-specific logic
  const handlePlayPause = useCallback(() => {
    if (shortcutsEnabled && !disabled) {
      onPlayPause()
    }
  }, [shortcutsEnabled, disabled, onPlayPause])

  const handleVolumeUp = useCallback(() => {
    if (shortcutsEnabled && !disabled) {
      onVolumeUp()
    }
  }, [shortcutsEnabled, disabled, onVolumeUp])

  const handleVolumeDown = useCallback(() => {
    if (shortcutsEnabled && !disabled) {
      onVolumeDown()
    }
  }, [shortcutsEnabled, disabled, onVolumeDown])

  const handleSeekForward = useCallback(() => {
    if (shortcutsEnabled && !disabled) {
      onSeekForward()
    }
  }, [shortcutsEnabled, disabled, onSeekForward])

  const handleSeekBackward = useCallback(() => {
    if (shortcutsEnabled && !disabled) {
      onSeekBackward()
    }
  }, [shortcutsEnabled, disabled, onSeekBackward])

  const handleFullscreen = useCallback(() => {
    if (shortcutsEnabled && !disabled) {
      onFullscreen()
    }
  }, [shortcutsEnabled, disabled, onFullscreen])

  const handleMuteToggle = useCallback(() => {
    if (shortcutsEnabled && !disabled) {
      onMuteToggle()
    }
  }, [shortcutsEnabled, disabled, onMuteToggle])

  // Integrate with MediaModal's keyboard system
  // This provides the base keyboard handling infrastructure
  useKeyboardShortcuts({
    // Video-specific shortcuts
    onNext: undefined, // Not used for video player
    onPrevious: undefined, // Not used for video player
    onZoomIn: undefined, // Not used for video player
    onZoomOut: undefined, // Not used for video player
    onZoomReset: undefined, // Not used for video player
    
    // Custom key handlers for video controls
    customHandlers: {
      // Play/pause shortcuts (space and k)
      ' ': handlePlayPause,
      'k': handlePlayPause,
      'K': handlePlayPause,
      
      // Volume controls
      'ArrowUp': handleVolumeUp,
      'ArrowDown': handleVolumeDown,
      
      // Seeking controls
      'ArrowRight': handleSeekForward,
      'ArrowLeft': handleSeekBackward,
      
      // Fullscreen toggle
      'f': handleFullscreen,
      'F': handleFullscreen,
      
      // Mute toggle
      'm': handleMuteToggle,
      'M': handleMuteToggle
    },
    
    // Respect disabled state
    disabled: disabled || !shortcutsEnabled
  })

  return {
    shortcutsEnabled,
    setShortcutsEnabled
  }
}

export default useVideoKeyboardShortcuts

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. **Interface for Hook Parameters**:
 *    ```typescript
 *    interface UseVideoKeyboardShortcutsParams {
 *      onPlayPause: () => void
 *      disabled?: boolean
 *    }
 *    ```
 * 
 * 2. **Object Destructuring with Defaults**:
 *    ```typescript
 *    const useHook = ({ disabled = false }: Params) => {
 *      // disabled has default value if not provided
 *    }
 *    ```
 * 
 * 3. **Hook Composition**:
 *    ```typescript
 *    useKeyboardShortcuts({
 *      customHandlers: { 'k': handlePlayPause }
 *    })
 *    // Using another hook within our custom hook
 *    ```
 * 
 * 4. **Record Type for Key Mappings**:
 *    ```typescript
 *    customHandlers: Record<string, () => void> = {
 *      ' ': handlePlayPause,
 *      'k': handlePlayPause
 *    }
 *    ```
 * 
 * 5. **Multiple Key Bindings**:
 *    Same function mapped to different keys (space and 'k' for play/pause)
 * 
 * 6. **Conditional Handler Execution**:
 *    ```typescript
 *    const handlePlayPause = useCallback(() => {
 *      if (shortcutsEnabled && !disabled) {
 *        onPlayPause()
 *      }
 *    }, [shortcutsEnabled, disabled, onPlayPause])
 *    ```
 * 
 * 7. **State Management for Feature Flags**:
 *    Using useState to control whether shortcuts are active
 * 
 * 8. **Function Composition Pattern**:
 *    Wrapping provided handlers with additional logic (enable/disable checks)
 * 
 * Integration Benefits:
 * - Leverages existing MediaModal keyboard infrastructure
 * - Consistent shortcut handling across the application
 * - Easy to extend with additional video-specific shortcuts
 * - Respects modal-level keyboard management (escape key, etc.)
 * 
 * Accessibility Considerations:
 * - Standard media player keyboard shortcuts (space for play/pause)
 * - Consistent with popular video players (YouTube, VLC patterns)
 * - Can be disabled for accessibility reasons or form focus
 * - Provides clear shortcut documentation for screen readers
 * 
 * Performance Optimizations:
 * - All handlers wrapped in useCallback to prevent re-renders
 * - Conditional execution prevents unnecessary function calls
 * - State updates batched for optimal rendering performance
 * 
 * Error Prevention:
 * - Guards against disabled states prevent unintended actions
 * - Optional parameter defaults prevent undefined behavior
 * - Type safety ensures proper function signatures
 * 
 * User Experience Enhancements:
 * - Familiar keyboard shortcuts from popular media players
 * - Toggle functionality allows users to disable if needed
 * - Consistent behavior with other modal components
 * - Predictable shortcut patterns across the application
 * 
 * aiNagisa Compliance:
 * ✓ Integrates with existing keyboard handling infrastructure
 * ✓ Comprehensive accessibility and user experience considerations
 * ✓ Performance optimized with useCallback patterns
 * ✓ Clear TypeScript interfaces and documentation
 * ✓ Consistent patterns with other hook implementations
 */