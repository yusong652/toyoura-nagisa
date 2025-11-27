import { AgentProfileType, AgentProfileInfo } from '@aiNagisa/core'

/**
 * AgentProfileSelector TypeScript type definitions.
 * 
 * Comprehensive type system for the agent profile selection component,
 * following aiNagisa's clean architecture principles with clear separation
 * between state, events, and component interfaces.
 */

// =============================================================================
// Core Component Types
// =============================================================================

export interface AgentProfileSelectorProps {
  // Props mode - pass data explicitly
  currentProfile?: AgentProfileType
  availableProfiles?: AgentProfileInfo[]
  onProfileChange?: (profile: AgentProfileType) => Promise<void>
  isLoading?: boolean
  
  // Context mode - use AgentContext automatically
  useContext?: boolean
  
  // Display options
  variant?: 'default' | 'compact'
  iconType?: 'emoji' | 'svg'
  showDescription?: boolean
  showToolCount?: boolean
  
  // Styling
  className?: string
  width?: string
}

export interface ProfileIconProps {
  profile: AgentProfileType
  size?: number
}

// =============================================================================
// Hook Return Types
// =============================================================================

export interface ProfileSelectorStateHookReturn {
  currentProfile: AgentProfileType | undefined
  availableProfiles: AgentProfileInfo[]
  isLoading: boolean
  currentProfileInfo: AgentProfileInfo | undefined
  error: string | null
}

export interface ProfileSelectorEventHandlers {
  handleProfileSelect: (profile: AgentProfileType) => Promise<void>
  handleToggleDropdown: () => void
  handleKeyDown: (event: React.KeyboardEvent) => void
  handleClickOutside: (event: MouseEvent) => void
}

export interface DropdownStateHookReturn {
  isOpen: boolean
  setIsOpen: (open: boolean) => void
  dropdownRef: React.RefObject<HTMLDivElement>
}

// =============================================================================
// Component-Specific Types
// =============================================================================

export interface ProfileButtonProps {
  currentProfileInfo: AgentProfileInfo
  isOpen: boolean
  isLoading: boolean
  isCompact: boolean
  iconType: 'emoji' | 'svg'
  showToolCount: boolean
  onClick: () => void
  onKeyDown: (event: React.KeyboardEvent) => void
}

export interface ProfileDropdownProps {
  isOpen: boolean
  availableProfiles: AgentProfileInfo[]
  currentProfile: AgentProfileType
  isCompact: boolean
  isLoading: boolean
  iconType: 'emoji' | 'svg'
  showDescription: boolean
  showToolCount: boolean
  onProfileSelect: (profile: AgentProfileType) => Promise<void>
}

export interface ProfileOptionProps {
  profile: AgentProfileInfo
  isSelected: boolean
  isLoading: boolean
  isCompact: boolean
  iconType: 'emoji' | 'svg'
  showDescription: boolean
  showToolCount: boolean
  onSelect: (profile: AgentProfileType) => Promise<void>
}

// =============================================================================
// Event Handler Types
// =============================================================================

export type ProfileChangeHandler = (profile: AgentProfileType) => Promise<void>
export type ToggleHandler = () => void
export type KeyDownHandler = (event: React.KeyboardEvent) => void
export type ClickOutsideHandler = (event: MouseEvent) => void

// =============================================================================
// Display Configuration Types
// =============================================================================

export type SelectorVariant = 'default' | 'compact'
export type IconType = 'emoji' | 'svg'

export interface DisplayConfig {
  variant: SelectorVariant
  iconType: IconType
  showDescription: boolean
  showToolCount: boolean
}

// =============================================================================
// Error Handling Types
// =============================================================================

export interface ProfileSelectorError {
  message: string
  code?: string
  retryable?: boolean
}

// =============================================================================
// Constants and Utilities
// =============================================================================

export const PROFILE_ORDER: AgentProfileType[] = [
  AgentProfileType.CODING,
  AgentProfileType.LIFESTYLE,
  AgentProfileType.PFC,
  AgentProfileType.GENERAL,
  AgentProfileType.DISABLED
]

// =============================================================================
// Type Guards and Utilities
// =============================================================================

export const isValidProfile = (profile: any): profile is AgentProfileType => {
  return Object.values(AgentProfileType).includes(profile)
}

export const isValidVariant = (variant: any): variant is SelectorVariant => {
  return variant === 'default' || variant === 'compact'
}

export const isValidIconType = (iconType: any): iconType is IconType => {
  return iconType === 'emoji' || iconType === 'svg'
}