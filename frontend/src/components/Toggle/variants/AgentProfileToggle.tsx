import React, { useState, useRef, useEffect } from 'react';
import { useAgent } from '../contexts/agent/AgentContext';
import { AgentProfileType } from '../types/agent';
import UnifiedErrorDisplay from './UnifiedErrorDisplay';
import { useErrorDisplay } from '../hooks/useErrorDisplay';
import './AgentProfileToggle.css';

// SVG icon components for different agent profiles
const ProfileIcon: React.FC<{ profile: AgentProfileType; size?: number }> = ({ profile, size = 16 }) => {
  const iconProps = {
    width: size,
    height: size,
    fill: "currentColor",
    viewBox: "0 0 16 16"
  };

  switch (profile) {
    case AgentProfileType.CODING:
      return (
        <svg {...iconProps}>
          <path d="M5.854 4.854a.5.5 0 1 0-.708-.708l-3.5 3.5a.5.5 0 0 0 0 .708l3.5 3.5a.5.5 0 0 0 .708-.708L2.707 8l3.147-3.146zm4.292 0a.5.5 0 0 1 .708-.708l3.5 3.5a.5.5 0 0 1 0 .708l-3.5 3.5a.5.5 0 0 1-.708-.708L13.293 8l-3.147-3.146z"/>
        </svg>
      );
    case AgentProfileType.LIFESTYLE:
      return (
        <svg {...iconProps}>
          <path d="M3.612 15.443c-.386.198-.824-.149-.746-.592l.83-4.73L.173 6.765c-.329-.314-.158-.888.283-.95l4.898-.696L7.538.792c.197-.39.73-.39.927 0l2.184 4.327 4.898.696c.441.062.612.636.282.95l-3.522 3.356.83 4.73c.078.443-.36.79-.746.592L8 13.187l-4.389 2.256z"/>
        </svg>
      );
    case AgentProfileType.GENERAL:
      return (
        <svg {...iconProps}>
          <path d="M6 12.5a.5.5 0 0 1 .5-.5h3a.5.5 0 0 1 0 1h-3a.5.5 0 0 1-.5-.5ZM3 8.062C3 6.76 4.235 5.765 5.53 5.886a26.58 26.58 0 0 0 4.94 0C11.765 5.765 13 6.76 13 8.062v1.157a.933.933 0 0 1-.765.935c-.845.147-2.34.346-4.235.346-1.895 0-3.39-.2-4.235-.346A.933.933 0 0 1 3 9.219V8.062Zm4.542-.827a.25.25 0 0 0-.217.068l-.92.9a24.767 24.767 0 0 1-1.871-.183.25.25 0 0 0-.068.495c.55.076 1.232.149 2.02.193a.25.25 0 0 0 .189-.071l.754-.736.847 1.71a.25.25 0 0 0 .404.062l.932-.97a25.286 25.286 0 0 0 1.922-.188.25.25 0 0 0-.068-.495c-.538.074-1.207.145-1.98.189a.25.25 0 0 0-.166.07l-.754.785-.842-1.71a.25.25 0 0 0-.182-.119Z"/>
          <path d="M8.5 1.866a1 1 0 1 0-1 0V3h-2A4.5 4.5 0 0 0 1 7.5V8a1 1 0 0 0-1 1v2a1 1 0 0 0 1 1v1a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-1a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1v-.5A4.5 4.5 0 0 0 10.5 3h-2V1.866ZM14 7.5V13a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V7.5A3.5 3.5 0 0 1 5.5 4h5A3.5 3.5 0 0 1 14 7.5Z"/>
        </svg>
      );
    case AgentProfileType.DISABLED:
      return (
        <svg {...iconProps}>
          <path d="M8 15A7 7 0 1 1 8 1a7 7 0 0 1 0 14zm0 1A8 8 0 1 0 8 0a8 8 0 0 0 0 16z"/>
          <path d="M4.646 4.646a.5.5 0 0 1 .708 0L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 0 1 0-.708z"/>
        </svg>
      );
    default:
      return null;
  }
};

/**
 * Modern dropdown-style agent profile toggle component.
 * Optimized with:
 * - Fixed width dropdown matching button size
 * - Clean SVG icons instead of emojis
 * - No checkmark indicator (background color shows active state)
 * - Compact layout for toolbar integration
 */
export const AgentProfileToggle: React.FC = () => {
  const { 
    currentProfile, 
    availableProfiles, 
    isProfileLoading,
    updateAgentProfile 
  } = useAgent();
  const { error, showTemporaryError, clearError } = useErrorDisplay();

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const profileOrder: AgentProfileType[] = [
    AgentProfileType.CODING,
    AgentProfileType.LIFESTYLE,
    AgentProfileType.GENERAL,
    AgentProfileType.DISABLED
  ];


  // Get current profile info for display
  const currentProfileInfo = availableProfiles.find(p => p.profile_type === currentProfile);

  // Handle profile selection
  const handleProfileSelect = async (profile: AgentProfileType): Promise<void> => {
    if (isProfileLoading || profile === currentProfile) {
      setIsOpen(false);
      return;
    }
    
    try {
      await updateAgentProfile(profile);
      setIsOpen(false); // Close dropdown after selection
    } catch (error) {
      console.error('Failed to change agent profile:', error);
      showTemporaryError('Failed to change agent profile. Please try again.', 4000);
      // Keep dropdown open on error so user can try again
    }
  };

  // Handle click outside to close dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent): void => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Handle keyboard navigation
  const handleKeyDown = (event: React.KeyboardEvent): void => {
    if (event.key === 'Escape') {
      setIsOpen(false);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setIsOpen(!isOpen);
    }
  };

  if (!currentProfileInfo) {
    return null; // Don't render if current profile info is not available
  }

  return (
    <div 
      ref={dropdownRef}
      className="agent-profile-toggle"
    >
      {/* Current Profile Button (Always Visible) */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        onKeyDown={handleKeyDown}
        disabled={isProfileLoading}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={`Current agent profile: ${currentProfileInfo.name}. Click to change profile.`}
        className={`agent-profile-button ${isProfileLoading ? 'loading' : ''} ${isOpen ? 'open' : ''}`}
      >
        <div className="agent-profile-content">
          <ProfileIcon profile={currentProfile} size={16} />
          <span className="agent-profile-name">
            {currentProfileInfo.name}
          </span>
        </div>
        
        {/* Loading spinner or dropdown arrow */}
        {isProfileLoading ? (
          <div className="agent-profile-spinner" />
        ) : (
          <svg
            width="12"
            height="8"
            viewBox="0 0 12 8"
            fill="none"
            className={`agent-profile-arrow ${isOpen ? 'rotated' : ''}`}
          >
            <path
              d="M1 1.5L6 6.5L11 1.5"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </button>

      {/* Dropdown Menu */}
      {isOpen && (
        <div
          role="listbox"
          className="agent-profile-dropdown"
        >
          {profileOrder.map((profileType, index) => {
            const profileInfo = availableProfiles.find(p => p.profile_type === profileType);
            if (!profileInfo) return null;
            
            const isActive = currentProfile === profileType;
            const isDisabled = isProfileLoading;

            return (
              <button
                key={profileType}
                onClick={() => handleProfileSelect(profileType)}
                disabled={isDisabled}
                role="option"
                aria-selected={isActive}
                title={profileInfo.description}
                className={`agent-profile-option ${isActive ? 'active' : ''}`}
              >
                <ProfileIcon profile={profileType} size={16} />
                <span className="agent-profile-option-name">
                  {profileInfo.name}
                </span>
              </button>
            );
          })}
        </div>
      )}

      <UnifiedErrorDisplay
        error={error}
        onClose={clearError}
      />
    </div>
  );
}; 