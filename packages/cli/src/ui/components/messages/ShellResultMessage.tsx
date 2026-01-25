/**
 * Shell Result Message Component
 * Displays shell command output in Claude Code style with plain text (no markdown)
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ShellResultHistoryItem } from '../../types.js';
import { colors, theme } from '../../colors.js';

interface ShellResultMessageProps {
  item: ShellResultHistoryItem;
  terminalWidth?: number;
}

export const ShellResultMessage: React.FC<ShellResultMessageProps> = ({ item, terminalWidth }) => {
  // Claude Code style: "  ⎿  " prefix (2 spaces + symbol + 2 spaces)
  const symbolPrefix = '  ⎿  ';

  // Determine what to display
  const hasStdout = item.stdout && item.stdout.trim();
  const hasStderr = item.stderr && item.stderr.trim();

  // If no output at all
  if (!hasStdout && !hasStderr) {
    return (
      <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
        <Text color={colors.primary}>{symbolPrefix}</Text>
        <Text color={theme.text.muted} dimColor>(no output)</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
      <Text color={colors.primary}>{symbolPrefix}</Text>
      <Box flexDirection="column">
        {/* stdout */}
        {hasStdout && (
          <Text color={theme.text.secondary} wrap="wrap">
            {item.stdout.trim()}
          </Text>
        )}
        {/* stderr (if present, shown after stdout) */}
        {hasStderr && (
          <Text color={theme.status.error} wrap="wrap">
            {item.stderr.trim()}
          </Text>
        )}
      </Box>
    </Box>
  );
};
