/**
 * useProfileManager Hook
 *
 * Manages agent profile state and API interactions.
 * Handles loading available profiles and switching between them.
 */

import { useState, useCallback } from 'react';
import { apiClient } from '@toyoura-nagisa/core';
import type { AgentProfileType, AgentProfileInfo } from '../types.js';

interface UseProfileManagerParams {
  defaultProfile?: AgentProfileType;
}

interface UseProfileManagerReturn {
  currentProfile: AgentProfileType;
  availableProfiles: AgentProfileInfo[];
  isProfileLoading: boolean;
  setProfile: (profile: AgentProfileType) => void;
  refreshProfiles: () => Promise<void>;
}

export function useProfileManager({
  defaultProfile = 'pfc_expert',
}: UseProfileManagerParams = {}): UseProfileManagerReturn {
  const [currentProfile, setCurrentProfile] = useState<AgentProfileType>(defaultProfile);
  const [availableProfiles, setAvailableProfiles] = useState<AgentProfileInfo[]>([]);
  const [isProfileLoading, setIsProfileLoading] = useState(false);

  const refreshProfiles = useCallback(async () => {
    setIsProfileLoading(true);
    try {
      // HttpClient unwraps ApiResponse, so we get ProfileListData directly
      const response = await apiClient.get<{
        profiles: AgentProfileInfo[];
      }>('/api/profiles');
      if (response.profiles) {
        setAvailableProfiles(response.profiles);
      }
    } catch (err) {
      console.error('[useProfileManager] Failed to fetch profiles:', err);
    } finally {
      setIsProfileLoading(false);
    }
  }, []);

  const setProfile = useCallback((profile: AgentProfileType) => {
    setCurrentProfile(profile);
  }, []);

  return {
    currentProfile,
    availableProfiles,
    isProfileLoading,
    setProfile,
    refreshProfiles,
  };
}
