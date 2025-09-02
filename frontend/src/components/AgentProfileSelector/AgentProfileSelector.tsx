import React from 'react'
import { useErrorDisplay } from '../../hooks/useErrorDisplay'
import UnifiedErrorDisplay from '../UnifiedErrorDisplay'
import { 
  useProfileSelectorState, 
  useProfileSelectorEvents, 
  useDropdownState 
} from './hooks'
import { ProfileButton, ProfileDropdown } from './components'
import { AgentProfileSelectorProps } from './types'
import './AgentProfileSelector.css'

/**
 * Unified Agent Profile Selector Component
 * 
 * Refactored according to aiNagisa's clean architecture standards with:
 * - Separation of concerns using custom hooks
 * - Modular component composition  
 * - Type-safe throughout with comprehensive TypeScript
 * - Multiple usage patterns (context vs props mode)
 * - Accessibility features built-in
 * 
 * Supports multiple modes:
 * - Context mode: Automatically uses AgentContext
 * - Props mode: Accept data through props for flexibility
 * 
 * Features:
 * - Compact mode for toolbars
 * - SVG or emoji icons
 * - Error handling with UnifiedErrorDisplay
 * - Customizable display options
 * - Keyboard navigation support
 * 
 * Args:
 *     Props mode data:
 *         - currentProfile?: AgentProfileType
 *         - availableProfiles?: AgentProfileInfo[]  
 *         - onProfileChange?: (profile: AgentProfileType) => Promise<void>
 *         - isLoading?: boolean
 *     
 *     Context mode:
 *         - useContext?: boolean (default: false)
 *     
 *     Display options:
 *         - variant?: 'default' | 'compact' (default: 'default')
 *         - iconType?: 'emoji' | 'svg' (default: 'emoji')
 *         - showDescription?: boolean (default: true)
 *         - showToolCount?: boolean (default: true)
 *     
 *     Styling:
 *         - className?: string
 *         - width?: string
 * 
 * Returns:
 *     JSX.Element | null: Complete profile selector or null if no data
 * 
 * TypeScript Learning Points:
 * - Custom hook composition for state management
 * - Component composition with child components
 * - Props destructuring with default values
 * - Conditional rendering patterns
 * - Error boundary integration
 */
export const AgentProfileSelector: React.FC<AgentProfileSelectorProps> = ({
  // Props mode data
  currentProfile: propCurrentProfile,
  availableProfiles: propAvailableProfiles,
  onProfileChange: propOnProfileChange,
  isLoading: propIsLoading = false,
  
  // Context mode
  useContext: useContextMode = false,
  
  // Display options
  variant = 'default',
  iconType = 'emoji',
  showDescription = true,
  showToolCount = true,
  
  // Styling
  className = '',
  width
}) => {
  // Custom hooks for separated concerns
  const { 
    currentProfile,
    availableProfiles,
    isLoading,
    currentProfileInfo,
    error: stateError 
  } = useProfileSelectorState(
    useContextMode,
    propCurrentProfile,
    propAvailableProfiles,
    propIsLoading
  )
  
  const { isOpen, setIsOpen, dropdownRef } = useDropdownState()
  
  const { 
    handleProfileSelect,
    handleToggleDropdown,
    handleKeyDown 
  } = useProfileSelectorEvents(
    useContextMode,
    propOnProfileChange,
    currentProfile,
    isLoading,
    isOpen,
    setIsOpen
  )
  
  const { error: displayError, clearError } = useErrorDisplay()
  
  // Early return if no valid data available
  if (!currentProfileInfo || !availableProfiles.length) {
    return null
  }

  const isCompact = variant === 'compact'
  const combinedError = stateError || displayError
  
  return (
    <div 
      className={`agent-profile-selector ${variant} ${className}`}
      ref={dropdownRef}
      style={{ width }}
    >
      {/* Main Profile Button */}
      <ProfileButton
        currentProfileInfo={currentProfileInfo}
        isOpen={isOpen}
        isLoading={isLoading}
        isCompact={isCompact}
        iconType={iconType}
        showToolCount={showToolCount}
        onClick={handleToggleDropdown}
        onKeyDown={handleKeyDown}
      />

      {/* Profile Selection Dropdown */}
      <ProfileDropdown
        isOpen={isOpen}
        availableProfiles={availableProfiles}
        currentProfile={currentProfile!}
        isCompact={isCompact}
        isLoading={isLoading}
        iconType={iconType}
        showDescription={showDescription}
        showToolCount={showToolCount}
        onProfileSelect={handleProfileSelect}
      />
      
      {/* Error Display (only in context mode) */}
      {useContextMode && combinedError && (
        <UnifiedErrorDisplay
          error={combinedError}
          onClose={clearError}
        />
      )}
    </div>
  )
}

export default AgentProfileSelector

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Advanced Props Destructuring:
 *    Multiple prop categories with default values and renaming
 * 
 * 2. Custom Hook Composition:
 *    Three hooks working together to manage complex state
 * 
 * 3. Component Composition Pattern:
 *    Main component orchestrates specialized child components
 * 
 * 4. Conditional Rendering Strategies:
 *    Early returns, ternary operators, and logical AND operators
 * 
 * 5. Type Assertion with Non-Null:
 *    currentProfile! when we know it's safe after validation
 * 
 * 6. Error Handling Integration:
 *    Multiple error sources combined for comprehensive error display
 * 
 * Benefits of This Architecture:
 * - Single Responsibility: Each hook and component has one concern
 * - Testability: Logic separated into testable hooks
 * - Reusability: Hooks can be reused in other components
 * - Performance: Memoized hooks prevent unnecessary re-renders
 * - Maintainability: Clear separation of concerns makes changes easier
 * - Accessibility: Built-in throughout all child components
 * - Type Safety: Complete TypeScript coverage with proper interfaces
 * 
 * aiNagisa Architecture Compliance:
 * ✓ Custom hooks for logic separation
 * ✓ Child components in /components subdirectory
 * ✓ Types defined in separate types file
 * ✓ Index files for clean imports
 * ✓ Comprehensive TypeScript documentation
 * ✓ Error handling with UnifiedErrorDisplay
 * ✓ Accessibility features throughout
 */