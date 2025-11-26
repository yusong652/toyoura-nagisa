/**
 * Header Component
 * Displays application title, agent profile, and status
 */

import React from 'react';
import { Box, Text } from 'ink';
import { useAppState } from '../contexts/AppStateContext.js';
import { theme } from '../colors.js';
import type { AgentProfileType } from '../types.js';

// Profile display info (GitHub-inspired colors)
const PROFILE_DISPLAY: Record<AgentProfileType, { color: string; name: string }> = {
  coding: { color: '#3fb950', name: 'Coding' },      // GitHub green
  lifestyle: { color: '#d29922', name: 'Lifestyle' }, // GitHub yellow
  pfc: { color: '#a371f7', name: 'PFC' },            // GitHub purple
  general: { color: '#8b949e', name: 'General' },    // GitHub gray
  disabled: { color: '#f85149', name: 'Disabled' },  // GitHub red
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
        <Text color={appState.memoryEnabled ? '#3fb950' : theme.text.muted}>
          {appState.memoryEnabled ? 'Memory ON' : 'Memory OFF'}
        </Text>
      </Box>
      <Box>
        <Text color={statusColor}>{statusText}</Text>
      </Box>
    </Box>
  );
};
