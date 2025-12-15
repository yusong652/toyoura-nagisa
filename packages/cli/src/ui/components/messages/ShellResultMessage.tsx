/**
 * Shell Result Message Component
 * Displays shell command output using unified markdown format
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ShellResultHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { MarkdownText } from '../MarkdownText.js';

interface ShellResultMessageProps {
  item: ShellResultHistoryItem;
  terminalWidth?: number;
}

export const ShellResultMessage: React.FC<ShellResultMessageProps> = ({ item, terminalWidth }) => {
  // Use same prefix width as assistant message for alignment
  const prefix = '  ';  // 2 spaces to align with "● " prefix (width 2)
  const prefixWidth = prefix.length;

  // Determine what to display
  const hasStdout = item.stdout && item.stdout.trim();
  const hasStderr = item.stderr && item.stderr.trim();

  // If no output at all
  if (!hasStdout && !hasStderr) {
    return (
      <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
        <Box width={prefixWidth} flexShrink={0}>
          <Text>{prefix}</Text>
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
            <Text>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <MarkdownText baseColor={theme.text.secondary}>
              {item.stdout.trim()}
            </MarkdownText>
          </Box>
        </Box>
      )}
      {/* stderr (if present) */}
      {hasStderr && (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <MarkdownText baseColor={theme.status.error}>
              {item.stderr.trim()}
            </MarkdownText>
          </Box>
        </Box>
      )}
    </Box>
  );
};
