/**
 * AgentProfileSelector components module exports.
 * 
 * Centralized exports for all profile selector UI components.
 * Following aiNagisa's modular component architecture pattern.
 * 
 * Usage:
 *     import { ProfileButton, ProfileDropdown, ProfileIcon } from './components'
 * 
 * Architecture:
 *     - ProfileIcon: SVG icon rendering for different profile types
 *     - ProfileButton: Main button that displays current profile
 *     - ProfileDropdown: Dropdown menu for profile selection
 * 
 * Component Responsibilities:
 * - Each component handles a single UI concern
 * - Props are strongly typed with TypeScript interfaces
 * - Accessibility features are built into each component
 * - Clean separation between display logic and business logic
 */

export { default as ProfileIcon } from './ProfileIcon'
export { default as ProfileButton } from './ProfileButton'
export { default as ProfileDropdown } from './ProfileDropdown'

// Re-export component prop types for convenience
export type { 
  ProfileIconProps,
  ProfileButtonProps,
  ProfileDropdownProps,
  ProfileOptionProps 
} from '../types'