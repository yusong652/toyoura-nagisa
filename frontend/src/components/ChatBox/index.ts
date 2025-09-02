/**
 * ChatBox module exports.
 * 
 * Main export point for the ChatBox component and its types.
 * The module is organized with clean architecture:
 * - Main component orchestrates the UI
 * - Sub-components handle specific responsibilities
 * - Hooks manage state and logic
 * - Types ensure type safety throughout
 */

// Main component
export { default as ChatBox } from './ChatBox'

// Sub-components (exported for testing or reuse)
export { default as ChatBoxTitleBar } from './components/ChatBoxTitleBar'
export { default as MessageList } from './components/MessageList'
export { default as ChatBoxControls } from './components/ChatBoxControls'
export { default as ShadowOverlay } from './components/ShadowOverlay'

// Hooks (exported for reuse in other components)
export { 
  useScrollBehavior, 
  useTitleManagement, 
  useMessageSelection 
} from './hooks'

// Types
export * from './types'