/**
 * AgentProfileSelector hooks module exports.
 * 
 * Centralized exports for all profile selector related custom hooks.
 * Following toyoura-nagisa's clean architecture pattern with organized hook modules.
 * 
 * Usage:
 *     import { useProfileSelectorState, useProfileSelectorEvents } from './hooks'
 * 
 * Architecture:
 *     - useProfileSelectorState: Manages data sources and computed state
 *     - useProfileSelectorEvents: Provides standardized event handlers  
 *     - useDropdownState: Handles dropdown visibility and click-outside behavior
 * 
 * TypeScript Benefits:
 * - Single import point for all hooks
 * - Type re-exports for convenience
 * - Clear module boundaries
 */

export { useProfileSelectorState } from './useProfileSelectorState'
export { useProfileSelectorEvents } from './useProfileSelectorEvents'
export { useDropdownState } from './useDropdownState'

// Re-export hook return types for convenience
export type { 
  ProfileSelectorStateHookReturn,
  ProfileSelectorEventHandlers,
  DropdownStateHookReturn 
} from '../types'