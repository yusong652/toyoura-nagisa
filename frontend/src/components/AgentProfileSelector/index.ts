/**
 * AgentProfileSelector module exports.
 * 
 * Main export point for the AgentProfileSelector component following
 * aiNagisa's clean architecture standards. Provides both default and
 * named exports for maximum flexibility.
 * 
 * Usage:
 *     // Default import (recommended)
 *     import AgentProfileSelector from './components/AgentProfileSelector'
 *     
 *     // Named import
 *     import { AgentProfileSelector } from './components/AgentProfileSelector'
 *     
 *     // Hook and component imports for advanced usage
 *     import { useProfileSelectorState } from './components/AgentProfileSelector'
 * 
 * Architecture:
 * - Main component: AgentProfileSelector.tsx
 * - Custom hooks: ./hooks/
 * - UI components: ./components/
 * - Types: ./types.ts
 * 
 * TypeScript Benefits:
 * - All exports properly typed
 * - Type re-exports for external usage
 * - Clear module boundaries
 * - IDE autocomplete support
 */

// Main component exports
export { default, AgentProfileSelector } from './AgentProfileSelector'

// Hook exports for advanced usage
export {
  useProfileSelectorState,
  useProfileSelectorEvents,
  useDropdownState
} from './hooks'

// Component exports for custom compositions
export {
  ProfileIcon,
  ProfileButton,
  ProfileDropdown
} from './components'

// Type exports for external TypeScript usage
export type {
  // Main component props
  AgentProfileSelectorProps,
  
  // Hook return types
  ProfileSelectorStateHookReturn,
  ProfileSelectorEventHandlers,
  DropdownStateHookReturn,
  
  // Component prop types
  ProfileIconProps,
  ProfileButtonProps,
  ProfileDropdownProps,
  
  // Utility types
  ProfileChangeHandler,
  SelectorVariant,
  IconType,
  DisplayConfig
} from './types'

// Constant exports
export { PROFILE_ORDER } from './types'