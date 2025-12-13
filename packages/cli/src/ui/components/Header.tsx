/**
 * Header Component
 * Displays application title, agent profile, status, and token usage
 */

import React from 'react';
import { Box, Text } from 'ink';
import { useAppState } from '../contexts/AppStateContext.js';
import { theme } from '../colors.js';
import type { AgentProfileType } from '../types.js';

interface HeaderProps {
  /** Whether shell mode is active (! prefix detected) */
  isShellMode?: boolean;
}

/**
 * Format tokens in K units (e.g., 128000 -> "128k")
 */
const formatTokensK = (tokens: number): string => {
  const k = Math.round(tokens / 1000);
  return `${k}k`;
};

// Profile display info (GitHub-inspired colors)
const PROFILE_DISPLAY: Record<AgentProfileType, { color: string; name: string }> = {
  coding: { color: '#3fb950', name: 'Coding' },      // GitHub green
  lifestyle: { color: '#d29922', name: 'Lifestyle' }, // GitHub yellow
  pfc: { color: '#a371f7', name: 'PFC' },            // GitHub purple
  general: { color: '#8b949e', name: 'General' },    // GitHub gray
  disabled: { color: '#f85149', name: 'Disabled' },  // GitHub red
};

export const Header: React.FC<HeaderProps> = ({ isShellMode = false }) => {
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

  // Calculate token usage display
  const usage = appState.tokenUsage;
  const tokensLeft = usage?.tokens_left ?? 128000;  // Default 128k
  const promptTokens = usage?.prompt_tokens ?? 0;
  const totalCapacity = promptTokens + tokensLeft;
  const remainingPercent = totalCapacity > 0
    ? Math.round((tokensLeft / totalCapacity) * 100)
    : 100;

  return (
    <Box flexDirection="row" justifyContent="space-between">
      <Box>
        <Text bold color={theme.text.accent}>
          toyoura-nagisa
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
        {isShellMode && (
          <>
            <Text color={theme.text.muted}> | </Text>
            <Text color={theme.status.warning} bold>SHELL</Text>
          </>
        )}
      </Box>
      <Box>
        <Text color={theme.text.muted}>
          usage: {remainingPercent}% ({formatTokensK(tokensLeft)})
        </Text>
        <Text color={theme.text.muted}> | </Text>
        <Text color={statusColor}>{statusText}</Text>
      </Box>
    </Box>
  );
};
