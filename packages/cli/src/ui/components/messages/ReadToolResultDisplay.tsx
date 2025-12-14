/**
 * Read Tool Result Display Component
 *
 * Specialized display for read tool results.
 * Removes line numbers from content and renders as clean text.
 * Works with both new tool results and historical session data.
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ToolResultHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { MarkdownText } from '../MarkdownText.js';

// Maximum lines to show before truncating
const MAX_RESULT_LINES = 10;
// Status indicator width (matches other tool displays)
const STATUS_INDICATOR_WIDTH = 3;

// Regex to detect line number format: "     1→content" or "    10→content"
const LINE_NUMBER_PATTERN = /^\s*\d+→/;

interface ReadToolResultDisplayProps {
  item: ToolResultHistoryItem;
  terminalWidth?: number;
  maxResultLines?: number;
}

/**
 * Get file name from path
 */
function getFileName(filePath: string): string {
  const parts = filePath.split(/[/\\]/);
  return parts[parts.length - 1] || filePath;
}

/**
 * Check if content has line number format from read tool
 */
function hasLineNumberFormat(content: string): boolean {
  const firstLine = content.split('\n')[0] || '';
  return LINE_NUMBER_PATTERN.test(firstLine);
}

/**
 * Remove line numbers from read tool output
 * Format: "     1→content" (spaces + number + arrow + content)
 */
function removeLineNumbers(content: string): string {
  const lines = content.split('\n');
  return lines.map(line => {
    // Match pattern: spaces + number + arrow + content
    const match = line.match(/^\s*\d+→(.*)$/);
    if (match) {
      return match[1];
    }
    return line;
  }).join('\n');
}

/**
 * Truncate content to maximum lines
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

export const ReadToolResultDisplay: React.FC<ReadToolResultDisplayProps> = ({
  item,
  terminalWidth: _terminalWidth,
  maxResultLines = MAX_RESULT_LINES,
}) => {
  const content = item.content || '';
  const filePath = item.file?.path || '';
  const fileName = filePath ? getFileName(filePath) : '';

  // Check if content has line number format and remove them
  const hasLineNumbers = hasLineNumberFormat(content);
  const cleanContent = hasLineNumbers ? removeLineNumbers(content) : content;
  const { text, truncated } = truncateContent(cleanContent.trimEnd(), maxResultLines);

  return (
    <Box flexDirection="column" paddingX={1} marginBottom={1}>
      {/* Header line - only show if we have a file name */}
      {fileName && (
        <Box paddingLeft={STATUS_INDICATOR_WIDTH + 1}>
          <Text bold color={theme.text.primary}>read</Text>
          <Text color={theme.text.secondary}> </Text>
          <Text color={theme.text.link}>{fileName}</Text>
        </Box>
      )}

      {/* Content - rendered as markdown without line numbers */}
      <Box paddingLeft={STATUS_INDICATOR_WIDTH}>
        <MarkdownText>{text}</MarkdownText>
      </Box>

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
