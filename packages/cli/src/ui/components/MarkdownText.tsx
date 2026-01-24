/**
 * Markdown Text Component
 * Lightweight markdown renderer for terminal
 *
 * Supports:
 * - **bold** text
 * - *italic* text
 * - `inline code`
 * - ```code blocks```
 * - # headings (h1-h6)
 * - - list items (with or without space after dash)
 * - 1. numbered lists
 * - > blockquotes
 * - --- horizontal rules
 * - | table | support |
 */

import React from 'react';
import { Text, Box } from 'ink';
import { theme } from '../colors.js';
import { getCachedStringWidth } from '../utils/textUtils.js';

interface MarkdownTextProps {
  children: string;
  /** Apply dim effect to all colors (for thinking blocks) */
  dimColor?: boolean;
  /** Base text color override (defaults to theme.text.primary) */
  baseColor?: string;
}

interface Segment {
  type: 'text' | 'bold' | 'italic' | 'code' | 'boldItalic' | 'strikethrough' | 'link' | 'underline' | 'mark' | 'kbd' | 'math';
  content: string;
  url?: string;  // For links
}

// Table alignment type
type TableAlignment = 'left' | 'center' | 'right';

/**
 * Simple syntax highlighting for code
 * Highlights: keywords, strings, numbers, comments
 */
interface CodeToken {
  type: 'keyword' | 'string' | 'number' | 'comment' | 'function' | 'operator' | 'text';
  content: string;
}

// Common programming keywords
const KEYWORDS = new Set([
  // Python
  'def', 'class', 'if', 'elif', 'else', 'for', 'while', 'try', 'except', 'finally',
  'with', 'as', 'import', 'from', 'return', 'yield', 'raise', 'pass', 'break',
  'continue', 'and', 'or', 'not', 'in', 'is', 'lambda', 'None', 'True', 'False',
  'async', 'await', 'global', 'nonlocal', 'assert', 'del',
  // JavaScript/TypeScript
  'const', 'let', 'var', 'function', 'async', 'await', 'return', 'if', 'else',
  'for', 'while', 'do', 'switch', 'case', 'break', 'continue', 'try', 'catch',
  'finally', 'throw', 'new', 'delete', 'typeof', 'instanceof', 'void', 'this',
  'super', 'class', 'extends', 'static', 'get', 'set', 'import', 'export',
  'default', 'from', 'as', 'null', 'undefined', 'true', 'false', 'of',
  // Common
  'print', 'console', 'log', 'error', 'warn', 'info',
]);

function tokenizeCode(code: string): CodeToken[] {
  const tokens: CodeToken[] = [];
  let remaining = code;

  while (remaining.length > 0) {
    // Single-line comment (// or #)
    let match = remaining.match(/^(\/\/.*|#.*)/);
    if (match) {
      tokens.push({ type: 'comment', content: match[1] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // String (double or single quotes, including template literals)
    match = remaining.match(/^(["'`])(?:[^\\]|\\.)*?\1/);
    if (match) {
      tokens.push({ type: 'string', content: match[0] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // Number (integer, float, hex)
    match = remaining.match(/^(0x[0-9a-fA-F]+|\d+\.?\d*(?:[eE][+-]?\d+)?)/);
    if (match) {
      tokens.push({ type: 'number', content: match[0] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // Word (identifier or keyword)
    match = remaining.match(/^[a-zA-Z_][a-zA-Z0-9_]*/);
    if (match) {
      const word = match[0];
      const type = KEYWORDS.has(word) ? 'keyword' : 'text';
      tokens.push({ type, content: word });
      remaining = remaining.slice(word.length);
      continue;
    }

    // Operators
    match = remaining.match(/^(=>|->|<=|>=|==|!=|&&|\|\||[+\-*/%=<>!&|^~])/);
    if (match) {
      tokens.push({ type: 'operator', content: match[0] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // Any other character
    tokens.push({ type: 'text', content: remaining[0] });
    remaining = remaining.slice(1);
  }

  return tokens;
}

/**
 * Render a line of code with syntax highlighting
 */
const CodeLine = React.memo<{ code: string; dimColor?: boolean }>(({ code, dimColor }) => {
  const tokens = tokenizeCode(code);

  return (
    <Text dimColor={dimColor}>
      {tokens.map((token, i) => {
        switch (token.type) {
          case 'keyword':
            return <Text key={i} color={theme.status.warning} bold>{token.content}</Text>;
          case 'string':
            return <Text key={i} color={theme.status.success}>{token.content}</Text>;
          case 'number':
            return <Text key={i} color={theme.text.accent}>{token.content}</Text>;
          case 'comment':
            return <Text key={i} color={theme.text.muted} italic>{token.content}</Text>;
          case 'operator':
            return <Text key={i} color={theme.status.info}>{token.content}</Text>;
          default:
            return <Text key={i} color={theme.text.primary}>{token.content}</Text>;
        }
      })}
    </Text>
  );
});

/**
 * Inline markdown patterns with their types
 * Order matters: more specific patterns first
 */
const INLINE_PATTERNS: Array<{
  pattern: RegExp;
  type: Segment['type'];
  getContent: (match: RegExpMatchArray) => { content: string; url?: string };
}> = [
  // HTML line break <br> or <br/> - convert to space in inline context
  {
    pattern: /^<br\s*\/?>/i,
    type: 'text',
    getContent: () => ({ content: ' ' }),
  },
  // Inline math $...$ (block math $$ handled separately in main loop)
  {
    pattern: /^\$([^$\n]+?)\$/,
    type: 'math',
    getContent: (m) => ({ content: m[1] }),
  },
  // Bold italic ***text*** or ___text___
  {
    pattern: /^(\*\*\*|___)(?=\S)([\s\S]*?\S)\1/,
    type: 'boldItalic',
    getContent: (m) => ({ content: m[2] }),
  },
  // Bold **text** or __text__
  {
    pattern: /^(\*\*|__)(?=\S)([\s\S]*?\S)\1/,
    type: 'bold',
    getContent: (m) => ({ content: m[2] }),
  },
  // Strikethrough ~~text~~
  {
    pattern: /^~~(?=\S)([\s\S]*?\S)~~/,
    type: 'strikethrough',
    getContent: (m) => ({ content: m[1] }),
  },
  // HTML underline <u>text</u>
  {
    pattern: /^<u>(?=\S)([\s\S]*?\S)<\/u>/i,
    type: 'underline',
    getContent: (m) => ({ content: m[1] }),
  },
  // HTML mark (highlight) <mark>text</mark>
  {
    pattern: /^<mark>(?=\S)([\s\S]*?\S)<\/mark>/i,
    type: 'mark',
    getContent: (m) => ({ content: m[1] }),
  },
  // HTML kbd (keyboard) <kbd>text</kbd>
  {
    pattern: /^<kbd>(?=\S)([\s\S]*?\S)<\/kbd>/i,
    type: 'kbd',
    getContent: (m) => ({ content: m[1] }),
  },
  // Italic *text* or _text_
  {
    pattern: /^(\*|_)(?=\S)([\s\S]*?\S)\1/,
    type: 'italic',
    getContent: (m) => ({ content: m[2] }),
  },
  // Inline code `text`
  {
    pattern: /^`(?=\S)([\s\S]*?\S)`/,
    type: 'code',
    getContent: (m) => ({ content: m[1] }),
  },
  // Link [text](url)
  {
    pattern: /^\[([^\]]+)\]\(([^)]+)\)/,
    type: 'link',
    getContent: (m) => ({ content: m[1], url: m[2] }),
  },
];


/**
 * Parse inline markdown within a line
 */
function parseInline(text: string): Segment[] {
  const segments: Segment[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    let matched = false;

    // Try each pattern
    for (const { pattern, type, getContent } of INLINE_PATTERNS) {
      // Special check for underscore italics to prevent matching inside words
      if (type === 'italic' && remaining.startsWith('_')) {
        // If it's an underscore, ensure it's not in the middle of a word
        const lastSeg = segments[segments.length - 1];
        if (lastSeg && lastSeg.type === 'text' && /\w$/.test(lastSeg.content)) {
          continue; // Skip underscore if preceded by a word character
        }
      }

      const match = remaining.match(pattern);
      if (match) {
        const { content, url } = getContent(match);
        segments.push({ type, content, url });
        remaining = remaining.slice(match[0].length);
        matched = true;
        break;
      }
    }

    if (!matched) {
      // Regular character - handle emojis/surrogate pairs correctly
      const char = Array.from(remaining)[0];
      const lastSeg = segments[segments.length - 1];
      if (lastSeg && lastSeg.type === 'text') {
        lastSeg.content += char;
      } else {
        segments.push({ type: 'text', content: char });
      }
      remaining = remaining.slice(char.length);
    }
  }

  return segments;
}

/**
 * Check if a line looks like a table row
 * A table row must:
 * - Start with | OR contain at least 2 | characters (column separators)
 * - Not be a list item or other markdown structure
 */
function isTableRow(line: string): boolean {
  const trimmed = line.trim();
  // Skip if it looks like a list item
  if (/^[-*]\s/.test(trimmed) || /^\d+\.\s/.test(trimmed)) {
    return false;
  }
  // Must start with | or contain at least 2 |
  const pipeCount = (trimmed.match(/\|/g) || []).length;
  return trimmed.startsWith('|') || pipeCount >= 2;
}

/**
 * Check if a line is a table separator row (contains only |, -, :, and spaces)
 */
function isTableSeparator(line: string): boolean {
  const trimmed = line.trim();
  return /^\|?[\s\-:|]+\|?$/.test(trimmed) && trimmed.includes('-');
}

/**
 * Parse table alignment from separator row
 */
function parseTableAlignments(separatorLine: string): TableAlignment[] {
  const cells = separatorLine.split('|').filter(cell => cell.trim() !== '');
  return cells.map(cell => {
    const trimmed = cell.trim();
    if (trimmed.startsWith(':') && trimmed.endsWith(':')) return 'center';
    if (trimmed.endsWith(':')) return 'right';
    return 'left';
  });
}

/**
 * Parse a table row into cells
 */
function parseTableRow(line: string): string[] {
  // Remove leading/trailing pipes and split
  const trimmed = line.trim();
  const withoutPipes = trimmed.startsWith('|') ? trimmed.slice(1) : trimmed;
  const withoutEndPipe = withoutPipes.endsWith('|') ? withoutPipes.slice(0, -1) : withoutPipes;
  return withoutEndPipe.split('|').map(cell => cell.trim());
}

/**
 * Strip markdown formatting to get plain text for width calculation
 * Returns the text AS IT WILL BE RENDERED (without hidden markers)
 * so that column width calculations match visual display.
 */
function stripMarkdownForWidth(text: string): string {
  const segments = parseInline(text);
  return segments.map(seg => seg.content).join('');
}

/**
 * Render inline segments
 */
const InlineLine = React.memo<{
  text: string;
  dimColor?: boolean;
  baseColor?: string;
}>(({ text, dimColor, baseColor }) => {
  const segments = parseInline(text);
  const textColor = baseColor || theme.text.primary;

  return (
    <Text wrap="wrap" dimColor={dimColor}>
      {segments.map((seg, i) => {
        switch (seg.type) {
          case 'bold':
            return <Text key={i} bold color={dimColor ? textColor : theme.text.accent}>{seg.content}</Text>;
          case 'italic':
            return <Text key={i} italic color={dimColor ? textColor : theme.status.info}>{seg.content}</Text>;
          case 'boldItalic':
            return <Text key={i} bold italic color={dimColor ? textColor : theme.text.accent}>{seg.content}</Text>;
          case 'code':
            // Inline code: Hide backticks and use vibrant color
            return (
              <Text key={i} color={dimColor ? theme.text.muted : theme.status.success} bold={!dimColor}>
                {seg.content}
              </Text>
            );

          case 'strikethrough':
            return <Text key={i} strikethrough color={theme.text.muted}>{seg.content}</Text>;
          case 'underline':
            return <Text key={i} underline color={textColor}>{seg.content}</Text>;
          case 'mark':
            // Highlight with inverse (background swap)
            return <Text key={i} inverse color={theme.status.warning}>{seg.content}</Text>;
          case 'kbd':
            // Keyboard key style with brackets
            return (
              <Text key={i}>
                <Text color={theme.text.muted}>[</Text>
                <Text bold color={theme.text.primary}>{seg.content}</Text>
                <Text color={theme.text.muted}>]</Text>
              </Text>
            );
          case 'math':
            // Inline math with special color
            return (
              <Text key={i}>
                <Text color={theme.text.muted}>$</Text>
                <Text italic color={theme.text.accent}>{seg.content}</Text>
                <Text color={theme.text.muted}>$</Text>
              </Text>
            );
          case 'link':
            // Display as text (url) with link color
            return (
              <Text key={i}>
                <Text color={theme.text.link} underline>{seg.content}</Text>
                <Text color={theme.text.muted}> ({seg.url})</Text>
              </Text>
            );
          default:
            return <Text key={i} color={textColor}>{seg.content}</Text>;
        }
      })}
    </Text>
  );
});

/**
 * Table renderer component
 * Supports inline markdown in cells: **bold**, *italic*, `code`, etc.
 */
const TableDisplay = React.memo<{
  headers: string[];
  alignments: TableAlignment[];
  rows: string[][];
  dimColor?: boolean;
  baseColor?: string;
}>(({ headers, alignments, rows, dimColor, baseColor }) => {
  const textColor = baseColor || theme.text.primary;

  // Calculate column widths using display width of STRIPPED content
  // This ensures markdown markers don't affect column sizing
  const columnCount = Math.max(headers.length, ...rows.map(r => r.length));
  const columnWidths: number[] = Array(columnCount).fill(3);

  // Update widths based on stripped content display width
  headers.forEach((header, i) => {
    const stripped = stripMarkdownForWidth(header);
    columnWidths[i] = Math.max(columnWidths[i] || 3, getCachedStringWidth(stripped));
  });
  rows.forEach(row => {
    row.forEach((cell, i) => {
      const stripped = stripMarkdownForWidth(cell);
      columnWidths[i] = Math.max(columnWidths[i] || 3, getCachedStringWidth(stripped));
    });
  });

  // Render a row of cells with markdown support
  const renderRow = (cells: string[], isHeader: boolean, key: string) => (
    <Box key={key} flexDirection="row">
      <Text color={theme.text.muted} dimColor={dimColor}>│</Text>
      {columnWidths.map((width, i) => {
        const cell = cells[i] || '';
        const align = alignments[i] || 'left';

        // Calculate padding based on stripped content width
        const strippedContent = stripMarkdownForWidth(cell);
        const contentWidth = getCachedStringWidth(strippedContent);
        const padding = Math.max(0, width - contentWidth);

        // Calculate left/right padding based on alignment
        let leftPad = 0;
        let rightPad = 0;
        switch (align) {
          case 'center':
            leftPad = Math.floor(padding / 2);
            rightPad = padding - leftPad;
            break;
          case 'right':
            leftPad = padding;
            break;
          default: // left
            rightPad = padding;
        }

        return (
          <React.Fragment key={i}>
            <Text color={theme.text.muted} dimColor={dimColor}> </Text>
            {leftPad > 0 && <Text>{' '.repeat(leftPad)}</Text>}
            {isHeader ? (
              <Text color={theme.status.info} bold dimColor={dimColor}>{strippedContent}</Text>
            ) : (
              <InlineLine text={cell} dimColor={dimColor} baseColor={baseColor} />
            )}
            {rightPad > 0 && <Text>{' '.repeat(rightPad)}</Text>}
            <Text color={theme.text.muted} dimColor={dimColor}> │</Text>
          </React.Fragment>
        );
      })}
    </Box>
  );

  // Render separator line
  const renderSeparator = (key: string, isTop = false, isBottom = false) => {
    const left = isTop ? '┌' : isBottom ? '└' : '├';
    const right = isTop ? '┐' : isBottom ? '┘' : '┤';
    const middle = isTop ? '┬' : isBottom ? '┴' : '┼';
    const line = columnWidths.map(w => '─'.repeat(w + 2)).join(middle);
    return (
      <Box key={key}>
        <Text color={theme.text.muted} dimColor={dimColor}>{left}{line}{right}</Text>
      </Box>
    );
  };

  return (
    <Box flexDirection="column">
      {renderSeparator('top', true)}
      {renderRow(headers, true, 'header')}
      {renderSeparator('header-sep')}
      {rows.map((row, i) => renderRow(row, false, `row-${i}`))}
      {renderSeparator('bottom', false, true)}
    </Box>
  );
});

export const MarkdownText: React.FC<MarkdownTextProps> = ({ children, dimColor, baseColor }) => {
  const lines = children.split('\n');
  const elements: React.ReactNode[] = [];
  const textColor = baseColor || theme.text.primary;

  let inCodeBlock = false;
  let codeLines: string[] = [];

  // Math block accumulator (for $$...$$)
  let inMathBlock = false;
  let mathLines: string[] = [];

  // Table accumulator
  let tableLines: string[] = [];
  let inTable = false;

  const flushTable = () => {
    if (tableLines.length >= 2) {
      // Need at least header + separator
      const headerLine = tableLines[0];
      const separatorLine = tableLines[1];

      if (isTableSeparator(separatorLine)) {
        const headers = parseTableRow(headerLine);
        const alignments = parseTableAlignments(separatorLine);
        const rows = tableLines.slice(2).map(parseTableRow);

        elements.push(
          <TableDisplay
            key={`table-${elements.length}`}
            headers={headers}
            alignments={alignments}
            rows={rows}
            dimColor={dimColor}
            baseColor={baseColor}
          />
        );
        tableLines = [];
        inTable = false;
        return true;
      }
    }
    // Not a valid table, render lines as regular text
    tableLines.forEach((tl, idx) => {
      elements.push(
        <Box key={`tl-${elements.length}-${idx}`}>
          <InlineLine text={tl} dimColor={dimColor} baseColor={baseColor} />
        </Box>
      );
    });
    tableLines = [];
    inTable = false;
    return false;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block delimiter
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim();
      // Flush any pending table
      if (inTable) flushTable();

      if (!inCodeBlock) {
        inCodeBlock = true;
        codeLines = [];
        // Render simple language label
        if (lang) {
          elements.push(
            <Box key={`lang-${i}`} marginBottom={0}>
              <Text color={theme.text.muted} italic>-- {lang} --</Text>
            </Box>
          );
        }
      } else {
        // End code block - render with syntax highlighting
        elements.push(
          <Box key={`code-${i}`} flexDirection="column">
            {codeLines.map((cl, j) => (
              <CodeLine key={j} code={cl} dimColor={dimColor} />
            ))}
          </Box>
        );
        inCodeBlock = false;
      }
      continue;
    }

    // Inside code block
    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    // Math block delimiter $$ (on its own line)
    if (line.trim() === '$$') {
      // Flush any pending table
      if (inTable) flushTable();

      if (!inMathBlock) {
        inMathBlock = true;
        mathLines = [];
      } else {
        // End math block - render accumulated lines
        elements.push(
          <Box key={`math-${i}`} flexDirection="column" marginY={0}>
            <Text color={theme.text.muted} dimColor={dimColor}>$$</Text>
            {mathLines.map((ml, j) => (
              <Text key={j} italic color={theme.text.accent} dimColor={dimColor}>  {ml}</Text>
            ))}
            <Text color={theme.text.muted} dimColor={dimColor}>$$</Text>
          </Box>
        );
        inMathBlock = false;
      }
      continue;
    }

    // Inside math block
    if (inMathBlock) {
      mathLines.push(line);
      continue;
    }

    // Table detection and accumulation
    if (isTableRow(line)) {
      tableLines.push(line);
      inTable = true;
      continue;
    } else if (inTable) {
      // End of table
      flushTable();
    }

    // Horizontal rule (---, ***, ___)
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(line.trim())) {
      elements.push(<Text key={`hr-${i}`} color={theme.text.muted} dimColor={dimColor}>───────────────────</Text>);
      continue;
    }

    // Heading (# text, ## text, etc.)
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const hColor = dimColor ? theme.text.muted : theme.status.info;
      elements.push(
        <Box key={`h-${i}`} marginTop={1} marginBottom={0}>
          <InlineLine text={headingMatch[2]} dimColor={dimColor} baseColor={hColor} />
        </Box>
      );
      continue;
    }

    // Blockquote (handles "> text", ">text", and empty ">")
    if (line.startsWith('>')) {
      // Extract content after '>' (with or without space)
      const quoteContent = line.startsWith('> ') ? line.slice(2) : line.slice(1);
      // Skip empty blockquotes (just ">")
      if (quoteContent.trim() === '') {
        continue;
      }
      elements.push(
        <Text key={`q-${i}`} color={theme.text.muted} italic dimColor={dimColor}>{quoteContent}</Text>
      );
      continue;
    }

    // List item - careful with asterisks to avoid matching **bold** or *italic*
    // - "-" can have optional space: "- text" or "-text"
    // - "*" MUST have space after it: "* text" (to distinguish from *italic* or **bold**)
    const dashListMatch = line.match(/^(\s*)-\s*(.+)$/);
    if (dashListMatch) {
      elements.push(
        <Box key={`li-${i}`} flexDirection="row">
          <Text color={theme.status.warning} dimColor={dimColor}>{dashListMatch[1]}- </Text>
          <InlineLine text={dashListMatch[2]} dimColor={dimColor} baseColor={baseColor} />
        </Box>
      );
      continue;
    }

    // Asterisk list requires space after * to avoid matching **bold** or *italic*
    const asteriskListMatch = line.match(/^(\s*)\*\s+(.+)$/);
    if (asteriskListMatch) {
      elements.push(
        <Box key={`li-${i}`} flexDirection="row">
          <Text color={theme.status.warning} dimColor={dimColor}>{asteriskListMatch[1]}- </Text>
          <InlineLine text={asteriskListMatch[2]} dimColor={dimColor} baseColor={baseColor} />
        </Box>
      );
      continue;
    }

    // Numbered list item (1. text, 2. text, etc.)
    const numberedListMatch = line.match(/^(\s*)(\d+)\.\s+(.+)$/);
    if (numberedListMatch) {
      elements.push(
        <Box key={`nli-${i}`} flexDirection="row">
          <Text color={theme.status.warning} dimColor={dimColor}>{numberedListMatch[1]}{numberedListMatch[2]}. </Text>
          <InlineLine text={numberedListMatch[3]} dimColor={dimColor} baseColor={baseColor} />
        </Box>
      );
      continue;
    }

    // Regular line
    elements.push(
      <Box key={`l-${i}`}>
        <InlineLine text={line} dimColor={dimColor} baseColor={baseColor} />
      </Box>
    );
  }

  // Handle unclosed code block
  if (inCodeBlock && codeLines.length > 0) {
    elements.push(
      <Box key="code-end" flexDirection="column">
        {codeLines.map((cl, j) => (
          <CodeLine key={j} code={cl} dimColor={dimColor} />
        ))}
      </Box>
    );
  }

  // Handle unclosed math block
  if (inMathBlock && mathLines.length > 0) {
    elements.push(
      <Box key="math-end" flexDirection="column">
        <Text color={theme.text.muted} dimColor={dimColor}>$$</Text>
        {mathLines.map((ml, j) => (
          <Text key={j} italic color={theme.text.accent} dimColor={dimColor}>  {ml}</Text>
        ))}
      </Box>
    );
  }

  // Flush any remaining table
  if (inTable) {
    flushTable();
  }

  return <Box flexDirection="column">{elements}</Box>;
};
