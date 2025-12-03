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
  isCompleted?: boolean;  // Tool execution has completed (has result)
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
  isCompleted = false,
  terminalWidth,
}) => {
  // Tool call shows:
  // - Blinking circle when executing (success color)
  // - Success/error icon when completed (colored by result)
  // - Empty circle ○ when pending (white color)
  let statusIndicator: React.ReactNode;
  let statusColor: string;
  const isError = item.isError === true;

  if (isExecuting) {
    statusIndicator = <BlinkingCircle color={theme.status.success} />;
    statusColor = theme.status.success;
  } else if (isCompleted) {
    statusColor = isError ? theme.status.error : theme.status.success;
    statusIndicator = isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  } else {
    statusColor = theme.text.primary;
    statusIndicator = TOOL_STATUS.PENDING;  // Empty circle ○ for pending
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
