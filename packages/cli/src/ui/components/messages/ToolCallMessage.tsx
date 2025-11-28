/**
 * Tool Call Message Component
 * Reference: Gemini CLI ui/components/messages/ToolMessage.tsx and ToolShared.tsx
 *
 * Displays tool calls in the Gemini CLI style with status indicator,
 * tool name, and description/command.
 *
 * Note: Diff visualization for edit/write tools is now shown in ToolResultMessage
 * after the tool execution completes (based on actual result, not input).
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ToolCallHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { TOOL_STATUS } from '../../markers.js';
import { BlinkingCircle } from '../BlinkingCircle.js';

// Status indicator width (matching Gemini CLI STATUS_INDICATOR_WIDTH = 3)
const STATUS_INDICATOR_WIDTH = 3;

interface ToolCallMessageProps {
  item: ToolCallHistoryItem;
  isExecuting?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  terminalWidth?: number;
}

/**
 * Get file name from path
 */
function getFileName(filePath: string): string {
  const parts = filePath.split(/[/\\]/);
  return parts[parts.length - 1] || filePath;
}

/**
 * Get tool description from input parameters
 */
function getToolDescription(toolName: string, input: Record<string, unknown>): string {
  // For edit/write tools, show file name
  if (toolName === 'edit' || toolName === 'write') {
    if (input.file_path !== undefined) {
      return getFileName(String(input.file_path));
    }
  }

  // Common tool input patterns
  if (input.command !== undefined) {
    return String(input.command);
  }
  if (input.file_path !== undefined) {
    return String(input.file_path);
  }
  if (input.path !== undefined) {
    return String(input.path);
  }
  if (input.pattern !== undefined) {
    return String(input.pattern);
  }
  if (input.query !== undefined) {
    return String(input.query);
  }
  if (input.url !== undefined) {
    return String(input.url);
  }
  // For other tools, show a summary of the input
  const keys = Object.keys(input);
  if (keys.length > 0) {
    const firstKey = keys[0];
    const value = input[firstKey];
    if (typeof value === 'string' && value.length < 100) {
      return value;
    }
    return `${firstKey}: ...`;
  }
  return '';
}

export const ToolCallMessage: React.FC<ToolCallMessageProps> = ({
  item,
  isExecuting = false,
  isSuccess = false,
  isError = false,
  terminalWidth,
}) => {
  // Determine status indicator and color
  let statusIndicator: React.ReactNode;
  let statusColor: string;

  if (isError) {
    statusIndicator = TOOL_STATUS.ERROR;
    statusColor = theme.status.error;
  } else if (isSuccess) {
    statusIndicator = TOOL_STATUS.SUCCESS;
    statusColor = theme.status.success;
  } else if (isExecuting) {
    statusColor = theme.status.warning;
    statusIndicator = <BlinkingCircle color={statusColor} />;
  } else {
    statusIndicator = TOOL_STATUS.PENDING;
    statusColor = theme.status.success;
  }

  const description = getToolDescription(item.toolName, item.toolInput);
  const boxWidth = terminalWidth ? terminalWidth : undefined;

  return (
    <Box paddingX={1} width={boxWidth} marginBottom={1}>
      <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
        <Text color={statusColor}>{statusIndicator}</Text>
      </Box>
      <Text wrap="truncate">
        <Text bold color={theme.text.primary}>
          {item.toolName}
        </Text>
        {description && (
          <Text color={theme.text.secondary}> {description}</Text>
        )}
      </Text>
    </Box>
  );
};
