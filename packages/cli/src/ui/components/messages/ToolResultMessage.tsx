/**
 * Tool Result Message Component
 * Reference: Gemini CLI ui/components/messages/ToolResultDisplay.tsx
 *
 * Displays tool execution results within the tool call box.
 * Shows output in a dimmed style, truncated if too long.
 * Special handling for edit/write tools to show diff visualization.
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ToolResultHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { TOOL_STATUS } from '../../markers.js';
import { DiffRenderer } from '../DiffRenderer.js';

// Maximum lines to show before truncating
const MAX_RESULT_LINES = 10;
const STATUS_INDICATOR_WIDTH = 3;
// Maximum height for diff display
const MAX_DIFF_HEIGHT = 15;

interface ToolResultMessageProps {
  item: ToolResultHistoryItem;
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

/**
 * Display for edit/write tool results with diff
 */
const DiffToolResultDisplay: React.FC<{
  item: ToolResultHistoryItem;
  terminalWidth?: number;
}> = ({ item, terminalWidth }) => {
  const diff = item.diff!;
  const fileName = getFileName(diff.file_path);
  const statusSymbol = item.isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  const statusColor = item.isError ? theme.status.error : theme.status.success;
  const contentWidth = terminalWidth ? terminalWidth - 4 : undefined;

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Tool header line */}
      <Box paddingX={1}>
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          <Text color={statusColor}>{statusSymbol}</Text>
        </Box>
        <Text bold color={theme.text.primary}>{item.toolName || 'edit'}</Text>
        <Text color={theme.text.secondary}> </Text>
        <Text color={theme.text.link}>{fileName}</Text>
        <Text color={theme.text.secondary}> </Text>
        <Text color={theme.status.success}>+{diff.additions}</Text>
        <Text color={theme.text.muted}>/</Text>
        <Text color={theme.status.error}>-{diff.deletions}</Text>
      </Box>

      {/* Diff content */}
      {diff.content && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH + 1} flexDirection="column">
          <DiffRenderer
            diffContent={diff.content}
            filename={fileName}
            maxWidth={contentWidth}
            maxHeight={MAX_DIFF_HEIGHT}
          />
        </Box>
      )}
    </Box>
  );
};

/**
 * Default tool result display (text output)
 * Shows tool name on first line, content on subsequent lines with consistent indentation
 */
const DefaultToolResultDisplay: React.FC<{
  item: ToolResultHistoryItem;
  terminalWidth?: number;
}> = ({ item, terminalWidth }) => {
  const statusSymbol = item.isError ? TOOL_STATUS.ERROR : TOOL_STATUS.SUCCESS;
  const statusColor = item.isError ? theme.status.error : theme.status.success;
  // Only trim trailing whitespace to preserve line number indentation
  // (some LLM APIs add trailing newlines, but leading spaces are part of formatting)
  const { text, truncated } = truncateContent(item.content.trimEnd(), MAX_RESULT_LINES);

  // Width constraint prevents Ink rendering bug with borders spanning multiple lines
  const boxWidth = terminalWidth ? terminalWidth : undefined;

  // Split into lines for individual rendering (preserves line formatting)
  const lines = text.split('\n');

  return (
    <Box
      flexDirection="column"
      paddingX={1}
      width={boxWidth}
      marginBottom={1}
    >
      {/* Header line: status + tool name */}
      <Box>
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          <Text color={statusColor}>{statusSymbol}</Text>
        </Box>
        <Text color={theme.text.secondary}>
          {item.toolName || 'tool result'}
        </Text>
      </Box>

      {/* Content lines - each line rendered separately to preserve formatting */}
      {lines.map((line, index) => (
        <Box key={index} paddingLeft={STATUS_INDICATOR_WIDTH}>
          <Text wrap="truncate-end" color={theme.text.secondary}>
            {line}
          </Text>
        </Box>
      ))}
      {truncated && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH}>
          <Text color={theme.text.muted}>
            ... (output truncated)
          </Text>
        </Box>
      )}
    </Box>
  );
};

export const ToolResultMessage: React.FC<ToolResultMessageProps> = ({ item, terminalWidth }) => {
  // If this is an edit/write tool with diff info, show diff visualization
  if (item.diff && item.diff.content && !item.isError) {
    return <DiffToolResultDisplay item={item} terminalWidth={terminalWidth} />;
  }

  // Default display for other tools or error cases
  return <DefaultToolResultDisplay item={item} terminalWidth={terminalWidth} />;
};
