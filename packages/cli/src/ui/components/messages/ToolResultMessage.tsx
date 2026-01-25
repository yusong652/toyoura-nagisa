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
import { DiffRenderer } from '../DiffRenderer.js';
import { MarkdownText } from '../MarkdownText.js';
import { useAppState } from '../../contexts/AppStateContext.js';
import { ReadToolResultDisplay } from './ReadToolResultDisplay.js';
import { TOOL_RESULT_PREFIX } from '../../markers.js';

// Maximum lines to show before truncating (Claude Code style: 3-4 lines)
const MAX_RESULT_LINES = 3;
// No limit when in full context mode
const MAX_RESULT_LINES_FULL = Infinity;
const STATUS_INDICATOR_WIDTH = 2;  // Match "● " prefix width
const RESULT_INDENT = STATUS_INDICATOR_WIDTH + 1;
// Maximum height for diff display
const MAX_DIFF_HEIGHT = 15;
const MAX_DIFF_HEIGHT_FULL = Infinity;

// Tools that output file paths - use plain text to avoid markdown rendering issues
// (e.g., file_name.py being rendered as italic due to underscores)
const PLAIN_TEXT_TOOLS = new Set([
  'glob', 'grep', 'bash', 'bash_output', 'kill_shell',
  'pfc_execute_task', 'pfc_check_task_status', 'pfc_list_tasks',
]);

const BASH_TOOLS = new Set(['bash', 'bash_output']);

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
function truncateContent(content: string, maxLines: number): { text: string; truncated: boolean; hiddenLines: number } {
  const lines = content.split('\n');
  if (lines.length <= maxLines) {
    return { text: content, truncated: false, hiddenLines: 0 };
  }
  return {
    text: lines.slice(0, maxLines).join('\n'),
    truncated: true,
    hiddenLines: lines.length - maxLines,
  };
}

/**
 * Display for edit/write tool results with diff
 * Note: Status indicator removed - success/error is shown on tool call block instead
 */
const DiffToolResultDisplay: React.FC<{
  item: ToolResultHistoryItem;
  terminalWidth?: number;
  maxDiffHeight: number;
}> = ({ item, terminalWidth, maxDiffHeight }) => {
  const diff = item.diff!;
  const fileName = getFileName(diff.file_path);
  const toolName = item.toolName?.toLowerCase();
  const isWriteTool = toolName === 'write';
  const isEditTool = toolName === 'edit';
  const isCompactHeader = isWriteTool || isEditTool;
  const contentWidth = terminalWidth ? terminalWidth - 4 : undefined;

  return (
    <Box flexDirection="column" marginBottom={1}>
      {/* Tool header line - no status indicator */}
      <Box paddingLeft={RESULT_INDENT}>
        {isCompactHeader ? (
          <>
            <Text color={theme.text.muted}>{TOOL_RESULT_PREFIX} </Text>
            <Text color={theme.status.success}>+{diff.additions}</Text>
            <Text color={theme.text.muted}>/</Text>
            <Text color={theme.status.error}>-{diff.deletions}</Text>
          </>
        ) : (
          <>
            <Text bold color={theme.text.primary}>{item.toolName || 'edit'}</Text>
            <Text color={theme.text.secondary}> </Text>
            <Text color={theme.text.link}>{fileName}</Text>
            <Text color={theme.text.secondary}> </Text>
            <Text color={theme.status.success}>+{diff.additions}</Text>
            <Text color={theme.text.muted}>/</Text>
            <Text color={theme.status.error}>-{diff.deletions}</Text>
          </>
        )}
      </Box>

      {/* Diff content */}
      {diff.content && (
        <Box paddingLeft={RESULT_INDENT + 2} flexDirection="column">
          <DiffRenderer
            diffContent={diff.content}
            filename={fileName}
            maxWidth={contentWidth}
            maxHeight={maxDiffHeight}
          />
        </Box>
      )}
    </Box>
  );
};

/**
 * Default tool result display (text output)
 * Shows content with markdown rendering and consistent indentation
 * Error results are displayed in red color
 * Note: Status indicator removed - success/error is shown on tool call block instead
 */
const DefaultToolResultDisplay: React.FC<{
  item: ToolResultHistoryItem;
  terminalWidth?: number;
  maxResultLines: number;
}> = ({ item, terminalWidth, maxResultLines }) => {
  // Only trim trailing whitespace to preserve line number indentation
  // (some LLM APIs add trailing newlines, but leading spaces are part of formatting)
  const { text, truncated, hiddenLines } = truncateContent(item.content.trimEnd(), maxResultLines);

  // Width constraint prevents Ink rendering bug with borders spanning multiple lines
  const boxWidth = terminalWidth ? terminalWidth : undefined;

  // Error results displayed in red
  const isError = item.isError === true;
  const textColor = isError ? theme.status.error : undefined;

  // Use plain text for file system tools to preserve path accuracy
  const usePlainText = isError || PLAIN_TEXT_TOOLS.has(item.toolName?.toLowerCase() || '');
  const isBashTool = BASH_TOOLS.has(item.toolName?.toLowerCase() || '');
  const showBashPrefix = isBashTool && !isError;

  return (
    <Box
      flexDirection="column"
      paddingX={1}
      width={boxWidth}
      marginBottom={1}
    >
      {/* Content - plain text for errors and file tools, markdown for others */}
      <Box paddingLeft={RESULT_INDENT} flexDirection="column">
        {isBashTool ? (
          <Box flexDirection="row">
            {showBashPrefix && (
              <Box width={2} flexShrink={0}>
                <Text color={theme.text.muted}>{TOOL_RESULT_PREFIX} </Text>
              </Box>
            )}
            <Box flexDirection="column" flexGrow={1}>
              {(text.length ? text.split('\n') : ['']).map((line, index) => (
                <Text key={index} color={textColor ?? theme.text.secondary} wrap="truncate-end">
                  {text.length === 0 ? '(no output)' : line}
                </Text>
              ))}
              {truncated && (
                <Text color={theme.text.muted}>
                  ... +{hiddenLines} lines (ctrl+o to expand)
                </Text>
              )}
            </Box>
          </Box>
        ) : usePlainText ? (
          <Text color={textColor}>{text}</Text>
        ) : (
          <MarkdownText>{text}</MarkdownText>
        )}
      </Box>
      {truncated && !isBashTool && (
        <Box paddingLeft={RESULT_INDENT}>
          <Text color={theme.text.muted}>
            ... +{hiddenLines} lines (ctrl+o to expand)
          </Text>
        </Box>
      )}
    </Box>
  );
};

export const ToolResultMessage: React.FC<ToolResultMessageProps> = ({ item, terminalWidth }) => {
  const { isFullContextMode } = useAppState();

  // Determine max lines based on mode
  const maxResultLines = isFullContextMode ? MAX_RESULT_LINES_FULL : MAX_RESULT_LINES;
  const maxDiffHeight = isFullContextMode ? MAX_DIFF_HEIGHT_FULL : MAX_DIFF_HEIGHT;

  // If this is an edit/write tool with diff info, show diff visualization
  if (item.diff && item.diff.content && !item.isError) {
    return <DiffToolResultDisplay item={item} terminalWidth={terminalWidth} maxDiffHeight={maxDiffHeight} />;
  }

  // If this is a read tool, use specialized display (removes line numbers)
  if (item.toolName === 'read' && !item.isError) {
    return <ReadToolResultDisplay item={item} terminalWidth={terminalWidth} maxResultLines={maxResultLines} />;
  }

  // Default display for other tools or error cases
  return <DefaultToolResultDisplay item={item} terminalWidth={terminalWidth} maxResultLines={maxResultLines} />;
};
