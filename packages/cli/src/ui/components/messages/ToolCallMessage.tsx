/**
 * Tool Call Message Component
 * Reference: Gemini CLI ui/components/messages/ToolMessage.tsx and ToolShared.tsx
 *
 * Displays tool calls in the Gemini CLI style with status indicator,
 * tool name, and description/command.
 *
 * Special handling for file modification tools (edit, write) to show
 * diff-style visualization of changes.
 */

import React, { useMemo } from 'react';
import { Box, Text } from 'ink';
import type { ToolCallHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { TOOL_STATUS } from '../../markers.js';
import { BlinkingCircle } from '../BlinkingCircle.js';
import { DiffRenderer, createDiff, getDiffStats } from '../DiffRenderer.js';

// Status indicator width (matching Gemini CLI STATUS_INDICATOR_WIDTH = 3)
const STATUS_INDICATOR_WIDTH = 3;

// Maximum height for diff display in history
const MAX_DIFF_HEIGHT = 15;

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
 * Get tool description from input parameters (for non-file-modification tools)
 */
function getToolDescription(_toolName: string, input: Record<string, unknown>): string {
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

/**
 * Render edit tool with diff visualization
 */
const EditToolDisplay: React.FC<{
  input: Record<string, unknown>;
  statusIndicator: React.ReactNode;
  statusColor: string;
  terminalWidth?: number;
}> = ({ input, statusIndicator, statusColor, terminalWidth }) => {
  const filePath = String(input.file_path || '');
  const oldString = String(input.old_string || '');
  const newString = String(input.new_string || '');
  const fileName = getFileName(filePath);

  // Generate diff from old_string and new_string
  const diffContent = useMemo(() => {
    if (!oldString && !newString) return '';
    return createDiff(fileName, oldString, newString, 3);
  }, [fileName, oldString, newString]);

  const diffStats = useMemo(() => getDiffStats(diffContent), [diffContent]);

  const contentWidth = terminalWidth ? terminalWidth - 4 : undefined;

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Tool header line */}
      <Box paddingX={1}>
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          <Text color={statusColor}>{statusIndicator}</Text>
        </Box>
        <Text bold color={theme.text.primary}>edit</Text>
        <Text color={theme.text.secondary}> </Text>
        <Text color={theme.text.link}>{fileName}</Text>
        <Text color={theme.text.secondary}> </Text>
        <Text color={theme.status.success}>+{diffStats.additions}</Text>
        <Text color={theme.text.muted}>/</Text>
        <Text color={theme.status.error}>-{diffStats.deletions}</Text>
      </Box>

      {/* Diff content */}
      {diffContent && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH + 1} flexDirection="column">
          <DiffRenderer
            diffContent={diffContent}
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
 * Render write tool with new file content preview
 */
const WriteToolDisplay: React.FC<{
  input: Record<string, unknown>;
  statusIndicator: React.ReactNode;
  statusColor: string;
  terminalWidth?: number;
}> = ({ input, statusIndicator, statusColor, terminalWidth }) => {
  const filePath = String(input.file_path || '');
  const content = String(input.content || '');
  const fileName = getFileName(filePath);

  // Generate diff for new file (empty old content)
  const diffContent = useMemo(() => {
    if (!content) return '';
    return createDiff(fileName, '', content, 3);
  }, [fileName, content]);

  const lineCount = content.split('\n').length;
  const contentWidth = terminalWidth ? terminalWidth - 4 : undefined;

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Tool header line */}
      <Box paddingX={1}>
        <Box width={STATUS_INDICATOR_WIDTH} flexShrink={0}>
          <Text color={statusColor}>{statusIndicator}</Text>
        </Box>
        <Text bold color={theme.text.primary}>write</Text>
        <Text color={theme.text.secondary}> </Text>
        <Text color={theme.text.link}>{fileName}</Text>
        <Text color={theme.text.secondary}> </Text>
        <Text color={theme.status.success} dimColor>(new file, {lineCount} lines)</Text>
      </Box>

      {/* File content preview */}
      {diffContent && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH + 1} flexDirection="column">
          <DiffRenderer
            diffContent={diffContent}
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
 * Default tool display (simple one-liner)
 */
const DefaultToolDisplay: React.FC<{
  item: ToolCallHistoryItem;
  statusIndicator: React.ReactNode;
  statusColor: string;
  terminalWidth?: number;
}> = ({ item, statusIndicator, statusColor, terminalWidth }) => {
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

  // Route to specialized display based on tool type
  if (item.toolName === 'edit') {
    return (
      <EditToolDisplay
        input={item.toolInput}
        statusIndicator={statusIndicator}
        statusColor={statusColor}
        terminalWidth={terminalWidth}
      />
    );
  }

  if (item.toolName === 'write') {
    return (
      <WriteToolDisplay
        input={item.toolInput}
        statusIndicator={statusIndicator}
        statusColor={statusColor}
        terminalWidth={terminalWidth}
      />
    );
  }

  // Default display for other tools
  return (
    <DefaultToolDisplay
      item={item}
      statusIndicator={statusIndicator}
      statusColor={statusColor}
      terminalWidth={terminalWidth}
    />
  );
};
