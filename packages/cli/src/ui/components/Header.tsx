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
  /** Whether PFC console mode is active (> prefix detected) */
  isPfcConsoleMode?: boolean;
  /** Current working directory for shell commands */
  cwd?: string | null;
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

/**
 * Format cwd for display, showing only the last part or truncating if too long
 */
const formatCwd = (cwd: string | null | undefined, maxLength: number = 30): string => {
  if (!cwd) return '~';

  // Get the last component of the path
  const parts = cwd.split('/').filter(Boolean);
  const lastPart = parts[parts.length - 1] || '~';

  // If the last part is short enough, show it
  if (lastPart.length <= maxLength) {
    return lastPart;
  }

  // Truncate with ellipsis
  return '...' + lastPart.slice(-(maxLength - 3));
};

export const Header: React.FC<HeaderProps> = ({ isShellMode = false, isPfcConsoleMode = false, cwd }) => {
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

  // Format cwd for display
  const displayCwd = formatCwd(cwd);

  return (
    <Box flexDirection="row" justifyContent="space-between">
      <Box>
        <Text bold color={theme.text.accent}>
          {displayCwd}
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
        {isPfcConsoleMode && (
          <>
            <Text color={theme.text.muted}> | </Text>
            <Text color={theme.status.info} bold>PFC</Text>
          </>
        )}
        {appState.isFullContextMode && (
          <>
            <Text color={theme.text.muted}> | </Text>
            <Text color={theme.status.info} bold>FULL</Text>
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
