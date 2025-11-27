/**
 * Diff Renderer Component
 * VSCode-style diff visualization for file changes
 *
 * Features:
 * - Clean, minimal design similar to VSCode diff view
 * - Background colors for added/removed lines
 * - Line numbers in gutter
 * - Truncation for long content with indicator
 */

import React, { useMemo } from 'react';
import { Box, Text } from 'ink';
import { theme } from '../colors.js';

interface DiffLine {
  type: 'add' | 'del' | 'context' | 'hunk' | 'other';
  oldLine?: number;
  newLine?: number;
  content: string;
}

/**
 * Parse unified diff format into structured lines with line numbers
 */
function parseDiffWithLineNumbers(diffContent: string): DiffLine[] {
  const lines = diffContent.split('\n');
  const result: DiffLine[] = [];
  let currentOldLine = 0;
  let currentNewLine = 0;
  let inHunk = false;
  const hunkHeaderRegex = /^@@ -(\d+),?\d* \+(\d+),?\d* @@/;

  for (const line of lines) {
    const hunkMatch = line.match(hunkHeaderRegex);
    if (hunkMatch) {
      currentOldLine = parseInt(hunkMatch[1], 10);
      currentNewLine = parseInt(hunkMatch[2], 10);
      inHunk = true;
      result.push({ type: 'hunk', content: line });
      // Adjust starting point for first line
      currentOldLine--;
      currentNewLine--;
      continue;
    }

    if (!inHunk) {
      // Skip standard Git header lines
      if (line.startsWith('--- ') || line.startsWith('+++ ') ||
          line.startsWith('diff ') || line.startsWith('index ')) {
        continue;
      }
      continue;
    }

    if (line.startsWith('+')) {
      currentNewLine++;
      result.push({
        type: 'add',
        newLine: currentNewLine,
        content: line.substring(1),
      });
    } else if (line.startsWith('-')) {
      currentOldLine++;
      result.push({
        type: 'del',
        oldLine: currentOldLine,
        content: line.substring(1),
      });
    } else if (line.startsWith(' ')) {
      currentOldLine++;
      currentNewLine++;
      result.push({
        type: 'context',
        oldLine: currentOldLine,
        newLine: currentNewLine,
        content: line.substring(1),
      });
    } else if (line.startsWith('\\')) {
      // Handle "\ No newline at end of file"
      result.push({ type: 'other', content: line });
    }
  }
  return result;
}

interface DiffRendererProps {
  /** The unified diff content to render */
  diffContent: string;
  /** The filename being diffed (for display and language detection) */
  filename?: string;
  /** Maximum width for the diff display */
  maxWidth?: number;
  /** Maximum height for the diff display (content exceeding this will be truncated) */
  maxHeight?: number;
}

// Default tab width for normalization
const DEFAULT_TAB_WIDTH = 4;

export const DiffRenderer: React.FC<DiffRendererProps> = ({
  diffContent,
  filename: _filename, // Reserved for future syntax highlighting
  maxWidth = 80,
  maxHeight,
}) => {
  const parsedLines = useMemo(() => {
    if (!diffContent || typeof diffContent !== 'string') {
      return [];
    }
    return parseDiffWithLineNumbers(diffContent);
  }, [diffContent]);

  const isNewFile = useMemo(() => {
    if (parsedLines.length === 0) return false;
    return parsedLines.every(
      (line) =>
        line.type === 'add' ||
        line.type === 'hunk' ||
        line.type === 'other'
    );
  }, [parsedLines]);

  const renderedOutput = useMemo(() => {
    if (!diffContent || typeof diffContent !== 'string') {
      return <Text color={theme.status.warning}>No diff content.</Text>;
    }

    if (parsedLines.length === 0) {
      return <Text color={theme.text.muted}>No changes detected.</Text>;
    }

    // For new files, show content with truncation
    if (isNewFile) {
      const addedLines = parsedLines
        .filter((line) => line.type === 'add')
        .map((line) => line.content);

      // Apply height limit with truncation
      let linesToShow = addedLines;
      let hiddenLines = 0;

      if (maxHeight && addedLines.length > maxHeight) {
        const visibleLines = maxHeight - 1;
        linesToShow = addedLines.slice(0, visibleLines);
        hiddenLines = addedLines.length - visibleLines;
      }

      // Calculate gutter width
      const gutterWidth = Math.max(3, addedLines.length.toString().length);
      const bgColor = theme.diff.addedBg;

      return (
        <Box flexDirection="column">
          {/* File content with line numbers */}
          {linesToShow.map((line, index) => (
            <Box key={index} flexDirection="row">
              {/* Line number gutter */}
              <Text color={theme.text.muted} backgroundColor={bgColor}>
                {(index + 1).toString().padStart(gutterWidth)}
              </Text>
              {/* Prefix symbol */}
              <Text color={theme.diff.addedText} backgroundColor={bgColor} bold>
                {' + '}
              </Text>
              {/* Line content */}
              <Text color={theme.text.primary} backgroundColor={bgColor}>
                {line}
              </Text>
            </Box>
          ))}

          {/* Truncation indicator */}
          {hiddenLines > 0 && (
            <Box marginTop={1}>
              <Text color={theme.text.muted}>
                {'─'.repeat(gutterWidth + 3)}
              </Text>
              <Text color={theme.text.muted}>
                {' '}↓ {hiddenLines} more line{hiddenLines > 1 ? 's' : ''} below
              </Text>
            </Box>
          )}
        </Box>
      );
    }

    // Render diff with line numbers
    return renderDiffContent(parsedLines, DEFAULT_TAB_WIDTH, maxWidth, maxHeight);
  }, [diffContent, parsedLines, isNewFile, maxWidth, maxHeight]);

  return <Box flexDirection="column">{renderedOutput}</Box>;
};

/**
 * Render diff content with VSCode-style visualization
 */
function renderDiffContent(
  parsedLines: DiffLine[],
  tabWidth: number,
  maxWidth: number,
  maxHeight?: number,
): React.ReactNode {
  // Normalize whitespace (replace tabs with spaces)
  const normalizedLines = parsedLines.map((line) => ({
    ...line,
    content: line.content.replace(/\t/g, ' '.repeat(tabWidth)),
  }));

  // Filter out non-displayable lines
  const displayableLines = normalizedLines.filter(
    (l) => l.type !== 'hunk' && l.type !== 'other'
  );

  if (displayableLines.length === 0) {
    return <Text color={theme.text.muted}>No changes detected.</Text>;
  }

  // Calculate gutter width based on max line number
  const maxLineNumber = Math.max(
    0,
    ...displayableLines.map((l) => l.oldLine ?? 0),
    ...displayableLines.map((l) => l.newLine ?? 0)
  );
  const gutterWidth = Math.max(3, maxLineNumber.toString().length);

  // Calculate minimum indentation for better display
  let baseIndentation = Infinity;
  for (const line of displayableLines) {
    if (line.content.trim() === '') continue;
    const firstCharIndex = line.content.search(/\S/);
    const currentIndent = firstCharIndex === -1 ? 0 : firstCharIndex;
    baseIndentation = Math.min(baseIndentation, currentIndent);
  }
  if (!isFinite(baseIndentation)) {
    baseIndentation = 0;
  }

  // Apply truncation if maxHeight is specified
  let linesToRender = displayableLines;
  let hiddenLines = 0;

  if (maxHeight && displayableLines.length > maxHeight) {
    const visibleLines = maxHeight - 1;
    linesToRender = displayableLines.slice(0, visibleLines);
    hiddenLines = displayableLines.length - visibleLines;
  }

  // Calculate content width for proper line display
  const contentWidth = Math.max(1, maxWidth - gutterWidth - 4); // 4 = gutter padding + prefix

  const content = linesToRender.map((line, index) => {
    const lineKey = `diff-line-${index}`;
    let gutterNumStr = '';
    let prefixChar = ' ';

    switch (line.type) {
      case 'add':
        gutterNumStr = (line.newLine ?? '').toString();
        prefixChar = '+';
        break;
      case 'del':
        gutterNumStr = (line.oldLine ?? '').toString();
        prefixChar = '-';
        break;
      case 'context':
        gutterNumStr = (line.newLine ?? '').toString();
        prefixChar = ' ';
        break;
      default:
        return null;
    }

    const displayContent = line.content.substring(baseIndentation);

    // Determine styling based on line type
    const isAdded = line.type === 'add';
    const isRemoved = line.type === 'del';
    const bgColor = isAdded ? theme.diff.addedBg : isRemoved ? theme.diff.removedBg : undefined;
    const prefixColor = isAdded ? theme.diff.addedText : isRemoved ? theme.diff.removedText : theme.text.muted;

    return (
      <Box key={lineKey} flexDirection="row">
        {/* Line number gutter */}
        <Text color={theme.text.muted} backgroundColor={bgColor}>
          {gutterNumStr.padStart(gutterWidth)}
        </Text>

        {/* Prefix symbol (+/-/space) */}
        <Text color={prefixColor} backgroundColor={bgColor} bold={isAdded || isRemoved}>
          {' '}{prefixChar}{' '}
        </Text>

        {/* Line content */}
        <Text
          color={theme.text.primary}
          backgroundColor={bgColor}
          wrap="truncate-end"
        >
          {displayContent}
          {/* Fill remaining width with background */}
          {bgColor && displayContent.length < contentWidth && (
            <Text backgroundColor={bgColor}>
              {' '.repeat(Math.max(0, contentWidth - displayContent.length))}
            </Text>
          )}
        </Text>
      </Box>
    );
  });

  return (
    <Box flexDirection="column">
      {/* Diff content */}
      {content}

      {/* Truncation indicator */}
      {hiddenLines > 0 && (
        <Box marginTop={1}>
          <Text color={theme.text.muted}>
            {'─'.repeat(gutterWidth + 3)}
          </Text>
          <Text color={theme.text.muted}>
            {' '}↓ {hiddenLines} more line{hiddenLines > 1 ? 's' : ''} below
          </Text>
        </Box>
      )}
    </Box>
  );
}

/**
 * Utility to create a unified diff string from old and new content
 */
export function createDiff(
  filename: string,
  oldContent: string,
  newContent: string,
  context = 3,
): string {
  // Use dynamic import to avoid bundling issues
  const Diff = require('diff');
  return Diff.createPatch(
    filename,
    oldContent,
    newContent,
    'Current',
    'Proposed',
    { context }
  );
}

/**
 * Compute diff statistics
 */
export function getDiffStats(diffContent: string): {
  additions: number;
  deletions: number;
} {
  const lines = diffContent.split('\n');
  let additions = 0;
  let deletions = 0;

  for (const line of lines) {
    if (line.startsWith('+') && !line.startsWith('+++')) {
      additions++;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      deletions++;
    }
  }

  return { additions, deletions };
}

/**
 * Get the total number of displayable lines in a diff
 */
export function getDiffLineCount(diffContent: string): number {
  if (!diffContent || typeof diffContent !== 'string') {
    return 0;
  }

  const lines = diffContent.split('\n');
  let count = 0;
  let inHunk = false;
  const hunkHeaderRegex = /^@@ -\d+,?\d* \+\d+,?\d* @@/;

  for (const line of lines) {
    if (hunkHeaderRegex.test(line)) {
      inHunk = true;
      continue;
    }

    if (!inHunk) continue;

    // Count add, del, and context lines
    if (line.startsWith('+') || line.startsWith('-') || line.startsWith(' ')) {
      count++;
    }
  }

  return count;
}
