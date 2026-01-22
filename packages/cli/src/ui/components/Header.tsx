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
  /** Whether shell command is currently executing */
  isShellExecuting?: boolean;
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

// Profile display info fallback (GitHub-inspired colors)
const PROFILE_DISPLAY: Record<AgentProfileType, { color: string; name: string }> = {
  pfc_expert: { color: '#a371f7', name: 'PFC Expert' }, // GitHub purple
  disabled: { color: '#f85149', name: 'Disabled' },     // GitHub red
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

export const Header: React.FC<HeaderProps> = ({ isShellMode = false, isShellExecuting = false, isPfcConsoleMode = false, cwd }) => {
  const appState = useAppState();
  const separator = <Text color={theme.text.muted}>  </Text>;

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
  const backendProfile = appState.availableProfiles.find(
    (profile) => profile.profile_type === appState.currentProfile
  );
  const profileInfo = {
    name: backendProfile?.name ?? PROFILE_DISPLAY[appState.currentProfile]?.name ?? appState.currentProfile,
    color: backendProfile?.color ?? PROFILE_DISPLAY[appState.currentProfile]?.color ?? theme.text.primary,
  };

  // Calculate token usage display
  const usage = appState.tokenUsage;
  const contextWindow = appState.contextWindow ?? 128000;
  const promptTokens = usage?.prompt_tokens ?? 0;
  const completionTokens = usage?.completion_tokens ?? 0;
  
  // Use tokens_left if provided, otherwise estimate from context window
  const tokensLeft = usage?.tokens_left ?? Math.max(0, contextWindow - promptTokens);
  
  // Usage is usually defined as (used / total)
  const usedTokens = promptTokens + completionTokens;
  const usedPercent = contextWindow > 0 
    ? Math.min(100, Math.round((usedTokens / contextWindow) * 100))
    : 0;

  // Format cwd for display
  const displayCwd = formatCwd(cwd);

  return (
    <Box flexDirection="row" justifyContent="space-between">
      <Box>
        <Text bold color={theme.text.accent}>
          {displayCwd}
        </Text>
        {appState.currentSessionId && (
          <>
            {separator}
            <Text color={theme.text.muted}>
              [{appState.currentSessionId.slice(0, 8)}]
            </Text>
          </>
        )}
        {separator}
        <Text color={profileInfo.color}>
          {profileInfo.name}
        </Text>
        {separator}
        <Text color={appState.memoryEnabled ? '#3fb950' : theme.text.muted}>
          {appState.memoryEnabled ? 'Memory ON' : 'Memory OFF'}
        </Text>
        {(isShellMode || isShellExecuting) && (
          <>
            {separator}
            {isShellExecuting ? (
              <>
                <Text color={theme.status.warning}>Running...</Text>
                <Text color={theme.text.muted}> (</Text>
                <Text color={theme.text.secondary}>Ctrl+B</Text>
                <Text color={theme.text.muted}> to background)</Text>
              </>
            ) : (
              <Text color={theme.status.warning} bold>SHELL</Text>
            )}
          </>
        )}
        {isPfcConsoleMode && (
          <>
            {separator}
            <Text color={theme.status.info} bold>PFC</Text>
          </>
        )}
        {appState.isFullContextMode && (
          <>
            {separator}
            <Text color={theme.status.info} bold>FULL</Text>
          </>
        )}
      </Box>
      <Box>
        <Text color={theme.text.muted}>
          usage: {usedPercent}% ({formatTokensK(usedTokens)}/{formatTokensK(contextWindow)})
        </Text>
        {separator}
        <Text color={statusColor}>{statusText}</Text>
      </Box>
    </Box>
  );
};
