/**
 * ChatBox hooks module exports.
 * 
 * Centralized exports for all ChatBox-related custom hooks,
 * providing clean imports for components using these hooks.
 * 
 * Usage:
 *     import { useScrollBehavior, useTitleManagement } from './hooks'
 * 
 * Architecture Pattern:
 *     - Each hook handles a specific concern
 *     - Hooks are composable and reusable
 *     - Type safety throughout with explicit return types
 */

export { useScrollBehavior } from './useScrollBehavior'
export { useTitleManagement } from './useTitleManagement'
export { useMessageSelection } from './useMessageSelection'

// Re-export hook return types for convenience
export type {
  UseScrollBehaviorReturn,
  UseTitleManagementReturn,
  UseMessageSelectionReturn
} from '../types'