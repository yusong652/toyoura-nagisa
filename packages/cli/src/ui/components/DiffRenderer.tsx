/**
 * Diff Renderer Component
 * Git diff-style visualization for file changes
 *
 * Reference: Gemini CLI ui/components/messages/DiffRenderer.tsx
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
  /** Maximum height for the diff display */
  maxHeight?: number;
}

// Default tab width for normalization
const DEFAULT_TAB_WIDTH = 4;

export const DiffRenderer: React.FC<DiffRendererProps> = ({
  diffContent,
  filename,
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
      return (
        <Box
          borderStyle="round"
          borderColor={theme.border.default}
          paddingX={1}
        >
          <Text color={theme.text.muted}>No changes detected.</Text>
        </Box>
      );
    }

    // For new files, just show the content without diff styling
    if (isNewFile) {
      const addedContent = parsedLines
        .filter((line) => line.type === 'add')
        .map((line) => line.content)
        .join('\n');

      return (
        <Box flexDirection="column">
          <Box marginBottom={1}>
            <Text color={theme.status.success} bold>
              + New file{filename ? `: ${filename}` : ''}
            </Text>
          </Box>
          <Box
            borderStyle="round"
            borderColor={theme.status.success}
            paddingX={1}
          >
            <Text color={theme.text.primary} wrap="wrap">
              {addedContent}
            </Text>
          </Box>
        </Box>
      );
    }

    // Render diff with line numbers
    return renderDiffContent(parsedLines, filename, DEFAULT_TAB_WIDTH, maxWidth, maxHeight);
  }, [diffContent, parsedLines, isNewFile, filename, maxWidth, maxHeight]);

  return <Box flexDirection="column">{renderedOutput}</Box>;
};

/**
 * Render diff content with line numbers and syntax highlighting
 */
function renderDiffContent(
  parsedLines: DiffLine[],
  filename: string | undefined,
  tabWidth: number,
  _maxWidth: number,
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
    return (
      <Box
        borderStyle="round"
        borderColor={theme.border.default}
        paddingX={1}
      >
        <Text color={theme.text.muted}>No changes detected.</Text>
      </Box>
    );
  }

  // Calculate gutter width based on max line number
  const maxLineNumber = Math.max(
    0,
    ...displayableLines.map((l) => l.oldLine ?? 0),
    ...displayableLines.map((l) => l.newLine ?? 0)
  );
  const gutterWidth = Math.max(1, maxLineNumber.toString().length);

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

  // Limit lines if maxHeight is specified
  let linesToRender = displayableLines;
  let truncatedCount = 0;
  if (maxHeight && displayableLines.length > maxHeight) {
    truncatedCount = displayableLines.length - maxHeight;
    linesToRender = displayableLines.slice(0, maxHeight);
  }

  const content = linesToRender.map((line, index) => {
    const lineKey = `diff-line-${index}`;
    let gutterNumStr = '';
    let prefixSymbol = ' ';

    switch (line.type) {
      case 'add':
        gutterNumStr = (line.newLine ?? '').toString();
        prefixSymbol = '+';
        break;
      case 'del':
        gutterNumStr = (line.oldLine ?? '').toString();
        prefixSymbol = '-';
        break;
      case 'context':
        gutterNumStr = (line.newLine ?? '').toString();
        prefixSymbol = ' ';
        break;
      default:
        return null;
    }

    const displayContent = line.content.substring(baseIndentation);

    // Determine colors based on line type
    const lineColor = line.type === 'add'
      ? theme.status.success
      : line.type === 'del'
        ? theme.status.error
        : theme.text.primary;

    const bgColor = line.type === 'add'
      ? '#1a3d1a'  // Dark green background
      : line.type === 'del'
        ? '#3d1a1a'  // Dark red background
        : undefined;

    return (
      <Box key={lineKey} flexDirection="row">
        {/* Line number gutter */}
        <Text color={theme.text.muted}>
          {gutterNumStr.padStart(gutterWidth)}{' '}
        </Text>

        {/* Diff line content */}
        <Text
          color={lineColor}
          backgroundColor={bgColor}
          wrap="truncate-end"
        >
          <Text color={lineColor} bold={line.type !== 'context'}>
            {prefixSymbol}
          </Text>
          {' '}
          {displayContent}
        </Text>
      </Box>
    );
  });

  return (
    <Box flexDirection="column">
      {/* File header if filename provided */}
      {filename && (
        <Box marginBottom={1}>
          <Text color={theme.text.accent} bold>
            {filename}
          </Text>
        </Box>
      )}

      {/* Diff content */}
      {content}

      {/* Truncation notice */}
      {truncatedCount > 0 && (
        <Box marginTop={1}>
          <Text color={theme.text.muted}>
            ... and {truncatedCount} more lines
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
