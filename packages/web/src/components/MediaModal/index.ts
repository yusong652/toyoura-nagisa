/**
 * MediaModal module exports.
 * 
 * Main export point for the MediaModal component and utilities.
 * Provides a base modal implementation that can be extended by
 * specific media viewers (ImageViewer, VideoPlayer, etc.).
 * 
 * Usage:
 *     // Default import
 *     import MediaModal from './components/MediaModal'
 *     
 *     // Named imports for hooks and components
 *     import { useMediaModal, MediaModalContainer } from './components/MediaModal'
 * 
 * Architecture:
 * - Main component: MediaModal.tsx
 * - Custom hooks: ./hooks/
 * - UI components: ./components/
 * - Types: ./types.ts
 * 
 * TypeScript Benefits:
 * - All exports properly typed
 * - Type re-exports for external usage
 * - Clear module boundaries
 */

// Main component export
export { default, default as MediaModal } from './MediaModal'

// Hook exports for custom implementations
export {
  useMediaModal,
  usePreventBodyScroll,
  useKeyboardShortcuts
} from './hooks'

// Component exports for custom compositions
export {
  MediaModalContainer,
  MediaModalHeader
} from './components'

// Type exports
export type {
  // Main component props
  MediaModalProps,
  
  // Component props
  MediaModalContainerProps,
  MediaModalHeaderProps,
  
  // Hook types
  UseMediaModalReturn,
  UseKeyboardShortcutsOptions,
  UsePreventBodyScrollOptions,
  
  // Utility types
  MediaType,
  MediaInfo,
  CloseReason,
  CloseEvent
} from './types'

// Constants
export { ANIMATION_DURATION, KEYBOARD_SHORTCUTS } from './types'