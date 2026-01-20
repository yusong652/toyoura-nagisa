/**
 * Read Tool Result Display Component
 *
 * Claude Code style display: shows "Read X lines" summary
 * instead of full content (user can view in IDE or with bash)
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ToolResultHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { TOOL_RESULT_PREFIX } from '../../markers.js';

// Status indicator width (matches other tool displays)
const STATUS_INDICATOR_WIDTH = 2;
const RESULT_INDENT = STATUS_INDICATOR_WIDTH + 1;

interface ReadToolResultDisplayProps {
  item: ToolResultHistoryItem;
  terminalWidth?: number;
  maxResultLines?: number;
}

/**
 * Count lines in content
 */
function countLines(content: string): number {
  if (!content || content.trim() === '') return 0;
  return content.split('\n').length;
}

export const ReadToolResultDisplay: React.FC<ReadToolResultDisplayProps> = ({
  item,
}) => {
  const content = item.content || '';
  const lineCount = countLines(content);

  // Claude Code style: "Read X lines"
  const summary = lineCount === 0
    ? 'Empty file'
    : lineCount === 1
    ? 'Read 1 line'
    : `Read ${lineCount} lines`;

  return (
    <Box paddingLeft={RESULT_INDENT} marginBottom={1}>
      <Text color={theme.text.muted}>{TOOL_RESULT_PREFIX} </Text>
      <Text color={theme.text.secondary}>{summary}</Text>
    </Box>
  );
};
