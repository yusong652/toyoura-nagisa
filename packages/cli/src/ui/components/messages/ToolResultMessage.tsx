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
import { theme } from '../../colors.js';
import { TOOL_STATUS } from '../../markers.js';

// Maximum lines to show before truncating
const MAX_RESULT_LINES = 10;
const STATUS_INDICATOR_WIDTH = 3;

interface ToolResultMessageProps {
  item: ToolResultHistoryItem;
  terminalWidth?: number;
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

export const ToolResultMessage: React.FC<ToolResultMessageProps> = ({ item, terminalWidth }) => {
  const statusSymbol = item.isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  const statusColor = item.isError ? theme.status.error : theme.status.success;
  // Trim whitespace for display (some LLM APIs add leading/trailing newlines)
  const { text, truncated } = truncateContent(item.content.trim(), MAX_RESULT_LINES);

  // Width constraint prevents Ink rendering bug with borders spanning multiple lines
  const boxWidth = terminalWidth ? terminalWidth : undefined;

  return (
    <Box
      paddingX={1}
      width={boxWidth}
      marginBottom={1}
    >
      <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
        <Text color={statusColor}>{statusSymbol}</Text>
      </Box>
      <Box flexDirection="column" flexGrow={1}>
        <Text wrap="wrap" color={theme.text.secondary}>
          {text}
        </Text>
        {truncated && (
          <Text color={theme.text.muted}>
            ... (output truncated)
          </Text>
        )}
      </Box>
    </Box>
  );
};
