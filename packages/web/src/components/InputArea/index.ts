/**
 * InputArea module exports.
 * 
 * Main export point for the InputArea component and related types.
 * Following toyoura-nagisa's clean architecture pattern with comprehensive
 * type exports and clear module boundaries.
 * 
 * Usage:
 *     import InputArea from './components/InputArea'
 *     // or
 *     import InputArea, { InputAreaProps } from './components/InputArea'
 * 
 * Architecture:
 * - InputArea: Main orchestrating component with clean architecture
 * - hooks/: Custom hooks for logic separation
 * - components/: Child components for UI sections  
 * - types.ts: Comprehensive TypeScript definitions
 * 
 * TypeScript Benefits:
 * - Single import point for main component
 * - Type re-exports for external usage
 * - Clear module structure
 * - IDE autocomplete support
 */

export { default } from './InputArea'

// Re-export types for external usage
export type {
  InputAreaProps,
  MessageInputInfo,
  SendingStatus,
  FileProcessingOptions,
  InputAreaConfig
} from './types'

// Re-export hook types if needed externally
export type {
  InputStateHookReturn,
  FileHandlingHookReturn,
  MessageSendingHookReturn,
  InputAutoResizeHookReturn
} from './types'