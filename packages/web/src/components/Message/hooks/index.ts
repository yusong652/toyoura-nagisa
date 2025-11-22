/**
 * Message hooks module exports.
 * 
 * Centralized exports for all message-related custom hooks. This index file
 * provides clean imports for components using message hooks.
 * 
 * Usage:
 *     import { useMessageState, useMessageEvents } from './hooks'
 * 
 * Architecture:
 *     - useMessageState: Manages display text, streaming chunks, and selection state
 *     - useMessageEvents: Provides standardized event handlers for interactions
 */

export { useMessageState } from './useMessageState'
export { useMessageEvents } from './useMessageEvents'

// Re-export types from the parent types file for convenience
export type { MessageStateHookReturn, MessageEventHandlers } from '../types'