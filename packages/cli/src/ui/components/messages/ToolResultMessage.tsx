/**
 * Tool Result Message Component
 * Reference: Gemini CLI ui/components/messages/ToolResultDisplay.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ToolResultHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

// Status symbols
const TOOL_STATUS = {
  SUCCESS: '✓',
  ERROR: '✕',
} as const;

interface ToolResultMessageProps {
  item: ToolResultHistoryItem;
}

export const ToolResultMessage: React.FC<ToolResultMessageProps> = ({ item }) => {
  const statusSymbol = item.isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  const statusColor = item.isError ? theme.status.error : theme.status.success;

  return (
    <Box flexDirection="column" marginY={1}>
      <Box flexDirection="row">
        <Box width={3} flexShrink={0}>
          <Text color={statusColor}>{statusSymbol}</Text>
        </Box>
        <Box flexGrow={1} flexDirection="column">
          <Text wrap="wrap" color={theme.text.secondary} dimColor>
            {item.content}
          </Text>
        </Box>
      </Box>
    </Box>
  );
};
