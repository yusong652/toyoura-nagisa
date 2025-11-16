/**
 * InputArea components module exports.
 * 
 * Centralized exports for all input area child components.
 * Following aiNagisa's clean architecture pattern with focused,
 * reusable components that handle specific UI concerns.
 * 
 * Usage:
 *     import { FilePreviewArea, MessageInput, InputControls } from './components'
 * 
 * Architecture:
 *     - FilePreviewArea: File thumbnail display and management
 *     - MessageInput: Enhanced textarea with auto-resize and shortcuts
 *     - InputControls: Action buttons (send, file upload) and toolbar integration
 * 
 * TypeScript Benefits:
 * - Single import point for all child components
 * - Type re-exports for component props
 * - Clear component boundaries
 * - IDE autocomplete support
 */

export { default as FilePreviewArea } from './FilePreviewArea'
export { default as MessageInput } from './MessageInput'
export { default as InputControls } from './InputControls'
export { default as SlashCommandSuggestions } from './SlashCommandSuggestions'
export { default as FileMentionSuggestions } from './FileMentionSuggestions'

// Re-export component prop types for convenience
export type {
  FilePreviewAreaProps,
  FilePreviewItemProps,
  MessageInputProps,
  InputControlsProps
} from '../types'