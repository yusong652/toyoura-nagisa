import React from 'react'
import ProfileIcon from './ProfileIcon'
import { ProfileDropdownProps, PROFILE_ORDER } from '../types'

/**
 * Profile dropdown menu component.
 * 
 * Renders a dropdown list of available profiles for selection. Supports
 * different display modes and handles profile ordering for consistent
 * user experience across the application.
 * 
 * Args:
 *     isOpen: Whether dropdown should be visible
 *     availableProfiles: List of available profiles to display
 *     currentProfile: Currently selected profile for highlighting
 *     isCompact: Whether to use compact layout
 *     isLoading: Loading state to disable interactions
 *     iconType: Icon display type ('emoji' | 'svg')
 *     showDescription: Whether to show profile descriptions
 *     showToolCount: Whether to show tool counts
 *     onProfileSelect: Handler for profile selection
 * 
 * Returns:
 *     JSX.Element | null: Dropdown menu or null when closed
 * 
 * TypeScript Learning Points:
 * - Early return for conditional rendering
 * - Array filtering and mapping with type safety
 * - Complex conditional rendering logic
 * - Event handler prop passing
 */
const ProfileDropdown: React.FC<ProfileDropdownProps> = ({
  isOpen,
  availableProfiles,
  currentProfile,
  isCompact,
  isLoading,
  iconType,
  showDescription,
  showToolCount,
  onProfileSelect
}) => {
  // Early return if dropdown is closed
  if (!isOpen) {
    return null
  }

  // Determine profile ordering based on variant
  const orderedProfiles = isCompact 
    ? PROFILE_ORDER
        .map(profileType => availableProfiles.find(p => p.profile_type === profileType))
        .filter((profile): profile is NonNullable<typeof profile> => profile !== undefined)
    : availableProfiles

  return (
    <div 
      className="profile-dropdown"
      role="listbox"
      aria-label="Select agent profile"
    >
      {orderedProfiles.map((profile) => {
        const isSelected = profile.profile_type === currentProfile
        
        return (
          <button
            key={profile.profile_type}
            className={`profile-option ${isSelected ? 'selected' : ''}`}
            onClick={() => onProfileSelect(profile.profile_type)}
            disabled={isLoading}
            role="option"
            aria-selected={isSelected}
            title={profile.description}
            style={{ '--profile-color': profile.color } as React.CSSProperties}
          >
            {/* Profile Icon */}
            {iconType === 'svg' ? (
              <ProfileIcon profile={profile.profile_type} size={16} />
            ) : (
              <span className="option-icon">{profile.icon}</span>
            )}
            
            {/* Profile Information */}
            {isCompact ? (
              <span className="agent-profile-option-name">{profile.name}</span>
            ) : (
              <div className="option-info">
                <span className="option-name">{profile.name}</span>
                {showDescription && (
                  <span className="option-description">{profile.description}</span>
                )}
                {showToolCount && (
                  <span className="option-tools">{profile.tool_count} tools</span>
                )}
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}

export default ProfileDropdown

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Early Return Pattern:
 *    Simplifies component logic by handling edge cases first
 * 
 * 2. Type Guards with Filter:
 *    filter((profile): profile is NonNullable<typeof profile> => ...)
 *    Ensures type safety after filtering undefined values
 * 
 * 3. Complex Conditional Logic:
 *    Ternary operators for different rendering modes
 * 
 * 4. CSS Custom Properties:
 *    style={{ '--profile-color': profile.color } as React.CSSProperties}
 *    Type-safe CSS variable assignment
 * 
 * 5. Role-Based Accessibility:
 *    listbox/option roles for proper screen reader support
 * 
 * Benefits of This Architecture:
 * - Flexible profile ordering based on display context
 * - Accessibility features integrated throughout
 * - Performance optimized with early returns
 * - Type-safe profile filtering and mapping
 * - Clean separation of compact vs full display modes
 */