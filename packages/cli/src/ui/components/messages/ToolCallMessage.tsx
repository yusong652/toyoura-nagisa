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
import { formatToolDisplay, getToolLayoutConfig, snakeToPascal } from '../../utils/toolFormat.js';

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
  const subagentType = isInvokeAgent ? snakeToPascal(String(item.toolInput.subagent_type || 'SubAgent')) : '';

  // Get tool-specific display formatting
  const toolDisplayResult = formatToolDisplay(item.toolName, item.toolInput);

  // Build full display text including multiline content
  const fullDisplay = toolDisplayResult.isMultiline && toolDisplayResult.additionalLines
    ? [toolDisplayResult.display, ...toolDisplayResult.additionalLines].join('\n')
    : toolDisplayResult.display;

  const boxWidth = terminalWidth ? terminalWidth : undefined;

  // Get tool-specific layout configuration
  const layoutConfig = getToolLayoutConfig(item.toolName);

  return (
    <Box width={boxWidth} marginBottom={layoutConfig.marginBottom}>
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
        // Tool-specific display format
        <Text wrap="wrap" bold color={theme.text.primary}>
          {fullDisplay}
        </Text>
      )}
    </Box>
  );
};
