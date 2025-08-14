import React, { useState, useEffect, useRef } from 'react';
import { AgentProfileType, AgentProfileInfo } from '../types/agent';
import './AgentProfileSelector.css';

interface AgentProfileSelectorProps {
  currentProfile: AgentProfileType;
  availableProfiles: AgentProfileInfo[];
  onProfileChange: (profile: AgentProfileType) => Promise<void>;
  isLoading?: boolean;
}

export const AgentProfileSelector: React.FC<AgentProfileSelectorProps> = ({
  currentProfile,
  availableProfiles,
  onProfileChange,
  isLoading = false
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentProfileInfo = availableProfiles.find(p => p.profile_type === currentProfile);
  
  const handleProfileSelect = async (profile: AgentProfileType) => {
    if (profile !== currentProfile && !isLoading) {
      setIsOpen(false);
      await onProfileChange(profile);
    }
  };

  const toggleDropdown = () => {
    if (!isLoading) {
      setIsOpen(!isOpen);
    }
  };

  return (
    <div className="agent-profile-selector" ref={dropdownRef}>
      <button 
        className={`profile-button ${isOpen ? 'open' : ''} ${isLoading ? 'loading' : ''}`}
        onClick={toggleDropdown}
        disabled={isLoading}
        title={currentProfileInfo?.description}
      >
        <span className="profile-icon">{currentProfileInfo?.icon}</span>
        <span className="profile-info">
          <span className="profile-name">{currentProfileInfo?.name}</span>
          <span className="profile-tools">
            {currentProfileInfo?.tool_count} tools
          </span>
        </span>
        <span className={`dropdown-arrow ${isOpen ? 'rotated' : ''}`}>▼</span>
      </button>

      {isOpen && (
        <div className="profile-dropdown">
          {availableProfiles.map((profile) => (
            <button
              key={profile.profile_type}
              className={`profile-option ${profile.profile_type === currentProfile ? 'selected' : ''}`}
              onClick={() => handleProfileSelect(profile.profile_type)}
              style={{ '--profile-color': profile.color } as React.CSSProperties}
            >
              <span className="option-icon">{profile.icon}</span>
              <div className="option-info">
                <span className="option-name">{profile.name}</span>
                <span className="option-description">{profile.description}</span>
                <span className="option-tools">{profile.tool_count} tools</span>
              </div>
              {profile.profile_type === currentProfile && (
                <span className="selected-indicator">✓</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};