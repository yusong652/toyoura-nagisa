/**
 * MediaModal hooks module exports.
 * 
 * Centralized exports for all media modal related custom hooks.
 * Following aiNagisa's clean architecture pattern with organized hook modules.
 * 
 * Usage:
 *     import { useMediaModal, useKeyboardShortcuts } from './hooks'
 * 
 * Architecture:
 *     - useMediaModal: Core modal behavior (background click, escape key)
 *     - usePreventBodyScroll: Prevent background scrolling when modal is open
 *     - useKeyboardShortcuts: Standardized keyboard interactions
 * 
 * TypeScript Benefits:
 * - Single import point for all hooks
 * - Type re-exports for convenience
 * - Clear module boundaries
 */

export { useMediaModal } from './useMediaModal'
export { usePreventBodyScroll } from './usePreventBodyScroll'
export { useKeyboardShortcuts } from './useKeyboardShortcuts'

// Re-export hook types for convenience
export type {
  UseMediaModalReturn,
  UseKeyboardShortcutsOptions,
  UsePreventBodyScrollOptions
} from '../types'