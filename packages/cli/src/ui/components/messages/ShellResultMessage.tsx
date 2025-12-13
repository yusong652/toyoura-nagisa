/**
 * Shell Result Message Component
 * Displays shell command output with distinct styling from INFO messages
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ShellResultHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface ShellResultMessageProps {
  item: ShellResultHistoryItem;
  terminalWidth?: number;
}

export const ShellResultMessage: React.FC<ShellResultMessageProps> = ({ item, terminalWidth }) => {
  // Use different prefix to distinguish from INFO (ℹ)
  const prefix = '  ';  // Indented to align with command output
  const prefixWidth = prefix.length;

  // Determine what to display
  const hasStdout = item.stdout && item.stdout.trim();
  const hasStderr = item.stderr && item.stderr.trim();

  // Choose color based on error status
  const textColor = item.isError ? theme.status.error : theme.text.secondary;

  // If no output at all
  if (!hasStdout && !hasStderr) {
    return (
      <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
        <Box width={prefixWidth} flexShrink={0}>
          <Text color={theme.text.muted}>{prefix}</Text>
        </Box>
        <Box flexGrow={1}>
          <Text wrap="wrap" color={theme.text.muted} dimColor>
            (no output)
          </Text>
        </Box>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" marginBottom={1} width={terminalWidth}>
      {/* stdout */}
      {hasStdout && (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.text.muted}>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <Text wrap="wrap" color={textColor}>
              {item.stdout.trim()}
            </Text>
          </Box>
        </Box>
      )}
      {/* stderr (if present and different from stdout) */}
      {hasStderr && (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.status.error}>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <Text wrap="wrap" color={theme.status.error}>
              {item.stderr.trim()}
            </Text>
          </Box>
        </Box>
      )}
    </Box>
  );
};
