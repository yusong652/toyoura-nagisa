/**
 * Tool Call Message Component
 * Reference: Gemini CLI ui/components/messages/ToolMessage.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import type { ToolCallHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

// Status symbols (matching Gemini CLI constants)
const TOOL_STATUS = {
  PENDING: 'o',
  EXECUTING: '*',
  SUCCESS: '✓',
  ERROR: '✕',
} as const;

interface ToolCallMessageProps {
  item: ToolCallHistoryItem;
  isExecuting?: boolean;
}

export const ToolCallMessage: React.FC<ToolCallMessageProps> = ({
  item,
  isExecuting = false,
}) => {
  const statusIndicator = isExecuting ? (
    <Spinner type="toggle" />
  ) : (
    TOOL_STATUS.PENDING
  );

  return (
    <Box flexDirection="column" marginY={1}>
      <Box flexDirection="row">
        <Box width={3} flexShrink={0}>
          <Text color={theme.status.warning}>{statusIndicator}</Text>
        </Box>
        <Box flexGrow={1}>
          <Text bold color={theme.text.primary}>
            {item.toolName}
          </Text>
          {item.toolInput.command !== undefined && (
            <Text color={theme.text.secondary}>
              {' '}{String(item.toolInput.command)}
            </Text>
          )}
        </Box>
      </Box>
    </Box>
  );
};
