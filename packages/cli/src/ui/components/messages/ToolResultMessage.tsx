/**
 * Tool Result Message Component
 * Reference: Gemini CLI ui/components/messages/ToolResultDisplay.tsx
 *
 * Displays tool execution results within the tool call box.
 * Shows output in a dimmed style, truncated if too long.
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ToolResultHistoryItem } from '../../types.js';
import { theme, TOOL_STATUS } from '../../colors.js';

// Maximum lines to show before truncating
const MAX_RESULT_LINES = 10;
const STATUS_INDICATOR_WIDTH = 3;

interface ToolResultMessageProps {
  item: ToolResultHistoryItem;
}

/**
 * Truncate content to a maximum number of lines
 */
function truncateContent(content: string, maxLines: number): { text: string; truncated: boolean } {
  const lines = content.split('\n');
  if (lines.length <= maxLines) {
    return { text: content, truncated: false };
  }
  return {
    text: lines.slice(0, maxLines).join('\n'),
    truncated: true,
  };
}

export const ToolResultMessage: React.FC<ToolResultMessageProps> = ({ item }) => {
  const statusSymbol = item.isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  const statusColor = item.isError ? theme.status.error : theme.status.success;
  const { text, truncated } = truncateContent(item.content, MAX_RESULT_LINES);

  return (
    <Box
      flexDirection="column"
      borderStyle="round"
      borderColor={theme.border.default}
      paddingX={1}
      marginY={0}
      marginTop={-1} // Merge with tool call box above
    >
      <Box flexDirection="row">
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          <Text color={statusColor}>{statusSymbol}</Text>
        </Box>
        <Box flexGrow={1} flexDirection="column">
          <Text wrap="wrap" color={theme.text.secondary} dimColor>
            {text}
          </Text>
          {truncated && (
            <Text color={theme.text.muted} dimColor>
              ... (output truncated)
            </Text>
          )}
        </Box>
      </Box>
    </Box>
  );
};
