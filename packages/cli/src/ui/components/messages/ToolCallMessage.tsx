/**
 * Tool Call Message Component
 *
 * Displays committed (historical) tool calls with Claude Code style formatting:
 * - Function call syntax: ToolName(param1: "value1", param2: "value2")
 * - All parameters visible at a glance
 *
 * Note: Pending tool calls during streaming are rendered by PendingItemDisplay.
 * Diff visualization is shown in ToolResultMessage after execution completes.
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ToolCallHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { TOOL_STATUS } from '../../markers.js';
import { formatToolParams } from '../../utils/toolFormat.js';

// Status indicator width (matching "● " prefix width = 2)
const STATUS_INDICATOR_WIDTH = 2;

interface ToolCallMessageProps {
  item: ToolCallHistoryItem;
  isCompleted?: boolean;  // Tool execution has completed (has result)
  terminalWidth?: number;
}

export const ToolCallMessage: React.FC<ToolCallMessageProps> = ({
  item,
  isCompleted = false,
  terminalWidth,
}) => {
  // Historical tool calls show:
  // - Success/error icon when completed (colored by result)
  // - Empty circle ○ when pending (white color)
  // Note: Pending/executing states are handled by PendingItemDisplay
  const isError = item.isError === true;
  const statusColor = isCompleted
    ? (isError ? theme.status.error : theme.status.success)
    : theme.text.primary;
  const statusIndicator = isCompleted
    ? (isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS)
    : TOOL_STATUS.PENDING;

  // Check if this is an invoke_agent call
  const isInvokeAgent = item.toolName === 'invoke_agent';
  const subagentType = isInvokeAgent ? String(item.toolInput.subagent_type || 'SubAgent') : '';

  // For invoke_agent: show description (task summary)
  // For standard tools: Claude Code style params
  const toolParams = formatToolParams(item.toolInput);

  const boxWidth = terminalWidth ? terminalWidth : undefined;

  return (
    <Box width={boxWidth} marginBottom={1}>
      <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
        <Text color={statusColor}>{statusIndicator}</Text>
      </Box>
      {isInvokeAgent ? (
        // Special display for invoke_agent: show SubAgent type with accent background
        <Text wrap="wrap">
          <Text bold color={theme.text.accent} inverse>
            {subagentType}
          </Text>
          {item.toolInput.description !== undefined && (
            <Text color={theme.text.secondary}> {String(item.toolInput.description)}</Text>
          )}
        </Text>
      ) : (
        // Claude Code style: ToolName(param1: "value1", param2: "value2")
        <Text wrap="wrap">
          <Text bold color={theme.text.primary}>
            {item.toolName}
          </Text>
          <Text color={theme.text.secondary}>
            ({toolParams})
          </Text>
        </Text>
      )}
    </Box>
  );
};
