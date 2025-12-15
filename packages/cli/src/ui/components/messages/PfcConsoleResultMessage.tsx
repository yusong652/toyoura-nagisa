/**
 * PFC Console Result Message Component
 * Displays PFC Python command output with distinct styling
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { PfcConsoleResultHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface PfcConsoleResultMessageProps {
  item: PfcConsoleResultHistoryItem;
  terminalWidth?: number;
}

export const PfcConsoleResultMessage: React.FC<PfcConsoleResultMessageProps> = ({ item, terminalWidth }) => {
  const prefix = '  ';  // Indented to align with command output
  const prefixWidth = prefix.length;

  // Check connection status first
  if (!item.connected) {
    return (
      <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
        <Box width={prefixWidth} flexShrink={0}>
          <Text color={theme.status.error}>{prefix}</Text>
        </Box>
        <Box flexGrow={1}>
          <Text wrap="wrap" color={theme.status.error}>
            PFC server not connected. Please start PFC server in PFC GUI.
          </Text>
        </Box>
      </Box>
    );
  }

  // Determine what to display
  const hasOutput = item.output && item.output.trim();
  const hasError = item.error && item.error.trim();
  const hasResult = item.result !== null && item.result !== undefined;

  // Choose color based on error status
  const textColor = item.isError ? theme.status.error : theme.text.secondary;

  // If no output at all
  if (!hasOutput && !hasError && !hasResult) {
    return (
      <Box flexDirection="column" marginBottom={1} width={terminalWidth}>
        {/* Task info */}
        {item.taskId && (
          <Box flexDirection="row">
            <Box width={prefixWidth} flexShrink={0}>
              <Text color={theme.text.muted}>{prefix}</Text>
            </Box>
            <Text color={theme.text.muted} dimColor>
              [task: {item.taskId}] {item.scriptName}
            </Text>
          </Box>
        )}
        {/* No output message */}
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.text.muted}>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <Text wrap="wrap" color={theme.text.muted} dimColor>
              (no output)
            </Text>
          </Box>
        </Box>
      </Box>
    );
  }

  return (
    <Box flexDirection="column" marginBottom={1} width={terminalWidth}>
      {/* Task info (subtle) */}
      {item.taskId && (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.text.muted}>{prefix}</Text>
          </Box>
          <Text color={theme.text.muted} dimColor>
            [task: {item.taskId}] {item.scriptName}
            {item.elapsedTime !== null && ` (${item.elapsedTime.toFixed(2)}s)`}
          </Text>
        </Box>
      )}

      {/* stdout */}
      {hasOutput && (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.text.muted}>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <Text wrap="wrap" color={textColor}>
              {item.output!.trim()}
            </Text>
          </Box>
        </Box>
      )}

      {/* result (if present and meaningful) */}
      {hasResult && (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.status.success}>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <Text wrap="wrap" color={theme.status.success}>
              {'>>> '}{typeof item.result === 'string' ? item.result : JSON.stringify(item.result)}
            </Text>
          </Box>
        </Box>
      )}

      {/* error (if present) */}
      {hasError && (
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={theme.status.error}>{prefix}</Text>
          </Box>
          <Box flexGrow={1}>
            <Text wrap="wrap" color={theme.status.error}>
              {item.error!.trim()}
            </Text>
          </Box>
        </Box>
      )}
    </Box>
  );
};
