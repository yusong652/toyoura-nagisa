/**
 * MediaModal components module exports.
 * 
 * Centralized exports for all media modal UI components.
 * Following toyoura-nagisa's modular component architecture pattern.
 * 
 * Usage:
 *     import { MediaModalContainer, MediaModalHeader } from './components'
 * 
 * Architecture:
 *     - MediaModalContainer: Inner container with click handling
 *     - MediaModalHeader: Consistent header with title and close button
 */

export { default as MediaModalContainer } from './MediaModalContainer'
export { default as MediaModalHeader } from './MediaModalHeader'

// Re-export component prop types for convenience
export type {
  MediaModalContainerProps,
  MediaModalHeaderProps
} from '../types'