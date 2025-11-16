/**
 * InputArea hooks module exports.
 * 
 * Centralized exports for all input area related custom hooks.
 * Following aiNagisa's clean architecture pattern with organized hook modules.
 * 
 * Usage:
 *     import { useInputState, useFileHandling, useMessageSending } from './hooks'
 * 
 * Architecture:
 *     - useInputState: Core state management (message, files, derived state)
 *     - useFileHandling: File operations (upload, paste, validation, removal)
 *     - useMessageSending: Send logic (validation, keyboard shortcuts, status)
 *     - useInputAutoResize: Textarea auto-resize functionality
 * 
 * TypeScript Benefits:
 * - Single import point for all hooks
 * - Type re-exports for convenience  
 * - Clear module boundaries
 * - IDE autocomplete support
 */

export { default as useInputState } from './useInputState'
export { default as useFileHandling } from './useFileHandling'
export { default as useMessageSending } from './useMessageSending'
export { default as useInputAutoResize } from './useInputAutoResize'
export { default as useSlashCommandDetection, BUILTIN_COMMANDS } from './useSlashCommandDetection'
export { useSlashCommandExecution } from './useSlashCommandExecution'
export { default as useFileSearch } from './useFileSearch'
export { default as useFileMentionDetection } from './useFileMentionDetection'

// Re-export hook return types for convenience
export type {
  InputStateHookReturn,
  FileHandlingHookReturn,
  MessageSendingHookReturn,
  InputAutoResizeHookReturn,
  SlashCommandDetectionHookReturn,
  SlashCommandExecutionHookReturn,
  FileSearchHookReturn,
  FileMentionDetectionHookReturn
} from '../types'