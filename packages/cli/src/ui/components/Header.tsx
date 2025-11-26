/**
 * Header Component
 * Displays application title, agent profile, and status
 */

import React from 'react';
import { Box, Text } from 'ink';
import { useAppState } from '../contexts/AppStateContext.js';
import { theme } from '../colors.js';
import type { AgentProfileType } from '../types.js';

// Profile display info (color)
const PROFILE_DISPLAY: Record<AgentProfileType, { color: string; name: string }> = {
  coding: { color: '#4CAF50', name: 'Coding' },
  lifestyle: { color: '#FF9800', name: 'Lifestyle' },
  pfc: { color: '#9C27B0', name: 'PFC' },
  general: { color: '#607D8B', name: 'General' },
  disabled: { color: '#F44336', name: 'Disabled' },
};

export const Header: React.FC = () => {
  const appState = useAppState();

  const statusColor =
    appState.connectionStatus === 'connected'
      ? theme.status.success
      : appState.connectionStatus === 'connecting'
        ? theme.status.warning
        : theme.status.error;

  const statusText =
    appState.connectionStatus === 'connected'
      ? 'Connected'
      : appState.connectionStatus === 'connecting'
        ? 'Connecting...'
        : 'Disconnected';

  // Get profile display info
  const profileInfo = PROFILE_DISPLAY[appState.currentProfile] || PROFILE_DISPLAY.general;

  return (
    <Box flexDirection="row" justifyContent="space-between" marginBottom={1}>
      <Box>
        <Text bold color={theme.text.accent}>
          aiNagisa
        </Text>
        {appState.currentSessionId && (
          <Text color={theme.text.muted}>
            {' '}[{appState.currentSessionId.slice(0, 8)}]
          </Text>
        )}
        <Text color={theme.text.muted}> | </Text>
        <Text color={profileInfo.color}>
          {profileInfo.name}
        </Text>
        <Text color={theme.text.muted}> | </Text>
        <Text color={appState.memoryEnabled ? '#4CAF50' : theme.text.muted}>
          {appState.memoryEnabled ? 'Memory ON' : 'Memory OFF'}
        </Text>
      </Box>
      <Box>
        <Text color={statusColor}>{statusText}</Text>
      </Box>
    </Box>
  );
};
