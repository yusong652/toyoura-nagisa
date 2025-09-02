import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AgentProfileType, AgentProfileInfo } from '../types/agent';
import { useAgent } from '../contexts/agent/AgentContext';
import UnifiedErrorDisplay from './UnifiedErrorDisplay';
import { useErrorDisplay } from '../hooks/useErrorDisplay';
import './AgentProfileSelector.css';

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

interface AgentProfileSelectorProps {
  // Props mode - pass data explicitly
  currentProfile?: AgentProfileType;
  availableProfiles?: AgentProfileInfo[];
  onProfileChange?: (profile: AgentProfileType) => Promise<void>;
  isLoading?: boolean;
  
  // Context mode - use AgentContext automatically
  useContext?: boolean;
  
  // Display options
  variant?: 'default' | 'compact';
  iconType?: 'emoji' | 'svg';
  showDescription?: boolean;
  showToolCount?: boolean;
  
  // Styling
  className?: string;
  width?: string;
}

/**
 * Unified Agent Profile Selector Component
 * 
 * Supports multiple modes:
 * - Context mode: Automatically uses AgentContext
 * - Props mode: Accept data through props for flexibility
 * 
 * Features:
 * - Compact mode for toolbars
 * - SVG or emoji icons
 * - Error handling
 * - Customizable display options
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
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  
  // Context integration
  const contextAgent = useAgent();
  const { error, showTemporaryError, clearError } = useErrorDisplay();
  
  // Determine data source (context vs props)
  const currentProfile = useContextMode ? contextAgent.currentProfile : propCurrentProfile;
  const availableProfiles = useContextMode ? contextAgent.availableProfiles : propAvailableProfiles;
  const isLoading = useContextMode ? contextAgent.isProfileLoading : propIsLoading;
  
  // Profile order for consistent display
  const profileOrder: AgentProfileType[] = [
    AgentProfileType.CODING,
    AgentProfileType.LIFESTYLE,
    AgentProfileType.GENERAL,
    AgentProfileType.DISABLED
  ];

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  const currentProfileInfo = availableProfiles?.find(p => p.profile_type === currentProfile);
  
  const handleProfileSelect = useCallback(async (profile: AgentProfileType) => {
    if (profile === currentProfile || isLoading) {
      setIsOpen(false);
      return;
    }
    
    try {
      if (useContextMode) {
        await contextAgent.updateAgentProfile(profile);
      } else if (propOnProfileChange) {
        await propOnProfileChange(profile);
      }
      setIsOpen(false);
    } catch (error) {
      console.error('Failed to change agent profile:', error);
      if (useContextMode) {
        showTemporaryError('Failed to change agent profile. Please try again.', 4000);
      }
    }
  }, [currentProfile, isLoading, useContextMode, contextAgent, propOnProfileChange, showTemporaryError]);

  const handleKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      setIsOpen(false);
    } else if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      setIsOpen(!isOpen);
    }
  }, [isOpen]);

  const toggleDropdown = () => {
    if (!isLoading) {
      setIsOpen(!isOpen);
    }
  };
  
  if (!currentProfileInfo || !availableProfiles) {
    return null;
  }

  const isCompact = variant === 'compact';
  
  return (
    <div 
      className={`agent-profile-selector ${variant} ${className}`}
      ref={dropdownRef}
      style={{ width }}
    >
      <button 
        className={`profile-button ${isOpen ? 'open' : ''} ${isLoading ? 'loading' : ''}`}
        onClick={toggleDropdown}
        onKeyDown={handleKeyDown}
        disabled={isLoading}
        title={currentProfileInfo?.description}
        aria-expanded={isOpen}
        aria-haspopup="listbox"
        aria-label={`Current agent profile: ${currentProfileInfo.name}. Click to change profile.`}
      >
        <div className="profile-content">
          {iconType === 'svg' ? (
            <ProfileIcon profile={currentProfile!} size={isCompact ? 16 : 18} />
          ) : (
            <span className="profile-icon">{currentProfileInfo?.icon}</span>
          )}
          
          {!isCompact && (
            <div className="profile-info">
              <span className="profile-name">{currentProfileInfo?.name}</span>
              {showToolCount && (
                <span className="profile-tools">
                  {currentProfileInfo?.tool_count} tools
                </span>
              )}
            </div>
          )}
          
          {isCompact && (
            <span className="profile-name-compact">{currentProfileInfo?.name}</span>
          )}
        </div>
        
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
            <span className={`dropdown-arrow ${isOpen ? 'rotated' : ''}`}>▼</span>
          )
        )}
      </button>

      {isOpen && (
        <div 
          className="profile-dropdown"
          role="listbox"
        >
          {(isCompact ? profileOrder : availableProfiles).map((item) => {
            // Handle different iteration types
            let profile: AgentProfileInfo;
            let profileType: AgentProfileType;
            
            if (isCompact) {
              // item is AgentProfileType
              profileType = item as AgentProfileType;
              const foundProfile = availableProfiles.find(p => p.profile_type === profileType);
              if (!foundProfile) return null;
              profile = foundProfile;
            } else {
              // item is AgentProfileInfo
              profile = item as AgentProfileInfo;
              profileType = profile.profile_type;
            }
            
            const isSelected = profileType === currentProfile;
            
            return (
              <button
                key={profileType}
                className={`profile-option ${isSelected ? 'selected' : ''}`}
                onClick={() => handleProfileSelect(profileType)}
                disabled={isLoading}
                role="option"
                aria-selected={isSelected}
                title={profile.description}
                style={{ '--profile-color': profile.color } as React.CSSProperties}
              >
                {iconType === 'svg' ? (
                  <ProfileIcon profile={profileType} size={16} />
                ) : (
                  <span className="option-icon">{profile.icon}</span>
                )}
                
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
            );
          })}
        </div>
      )}
      
      {useContextMode && (
        <UnifiedErrorDisplay
          error={error}
          onClose={clearError}
        />
      )}
    </div>
  );
};