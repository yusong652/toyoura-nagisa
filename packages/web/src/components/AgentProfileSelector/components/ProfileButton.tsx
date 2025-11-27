import React from 'react'
import ProfileIcon from './ProfileIcon'
import { ProfileButtonProps } from '../types'

/**
 * Profile selection button component.
 * 
 * Renders the main button that displays the current profile and toggles
 * the dropdown. Supports both compact and full variants with different
 * icon types and loading states.
 * 
 * Args:
 *     currentProfileInfo: Current profile information to display
 *     isOpen: Whether dropdown is currently open
 *     isLoading: Loading state for interaction prevention
 *     isCompact: Whether to use compact layout for toolbars
 *     iconType: Icon display type ('emoji' | 'svg')
 *     showToolCount: Whether to display tool count
 *     onClick: Click handler for button
 *     onKeyDown: Keyboard navigation handler
 * 
 * Returns:
 *     JSX.Element: Complete profile button with content and indicators
 * 
 * TypeScript Learning Points:
 * - Component composition with child components
 * - Conditional rendering based on props
 * - CSS custom properties for theming
 * - Accessibility attributes for screen readers
 */
const ProfileButton: React.FC<ProfileButtonProps> = ({
  currentProfileInfo,
  isOpen,
  isLoading,
  isCompact,
  iconType,
  showToolCount,
  onClick,
  onKeyDown
}) => {
  return (
    <button 
      className={`profile-button ${isOpen ? 'open' : ''} ${isLoading ? 'loading' : ''}`}
      onClick={onClick}
      onKeyDown={onKeyDown}
      disabled={isLoading}
      title={currentProfileInfo.description}
      aria-expanded={isOpen}
      aria-haspopup="listbox"
      aria-label={`Current agent profile: ${currentProfileInfo.name}. Click to change profile.`}
    >
      <div className="profile-content">
        {/* Profile Icon */}
        {iconType === 'svg' ? (
          <ProfileIcon profile={currentProfileInfo.profile_type} size={isCompact ? 16 : 18} />
        ) : (
          <span className="profile-icon">{currentProfileInfo.icon}</span>
        )}
        
        {/* Profile Information */}
        {!isCompact ? (
          <div className="profile-info">
            <span className="profile-name">{currentProfileInfo.name}</span>
            {showToolCount && (
              <span className="profile-tools">
                {currentProfileInfo.tool_count} tools
              </span>
            )}
          </div>
        ) : (
          <span className="profile-name-compact">{currentProfileInfo.name}</span>
        )}
      </div>
      
      {/* Loading Spinner or Dropdown Arrow */}
      {isLoading ? (
        <div className="profile-spinner" />
      ) : (
        iconType === 'svg' ? (
          <svg
            width="12"
            height="8"
            viewBox="0 0 12 8"
            fill="none"
            className={`dropdown-arrow-svg ${isOpen ? 'rotated' : ''}`}
            aria-hidden="true"
          >
            <path
              d="M1 1.5L6 6.5L11 1.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        ) : (
          <span className={`dropdown-arrow ${isOpen ? 'rotated' : ''}`} aria-hidden="true">
            ▼
          </span>
        )
      )}
    </button>
  )
}

export default ProfileButton

/**
 * TypeScript Concepts Demonstrated:
 * 
 * 1. Props Destructuring:
 *    Clean parameter extraction from props object
 * 
 * 2. Conditional Rendering:
 *    Multiple ternary operators for different display modes
 * 
 * 3. Template Literals:
 *    Dynamic className construction with state-based classes
 * 
 * 4. Accessibility Features:
 *    ARIA attributes for proper screen reader support
 * 
 * 5. Component Composition:
 *    ProfileIcon component integration with typed props
 * 
 * Benefits of This Architecture:
 * - Single responsibility for button display logic
 * - Supports multiple variants (compact/full, svg/emoji)
 * - Accessibility features built-in
 * - Loading states handled gracefully
 * - Clean separation from dropdown logic
 */