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
 * - - list items
 * - > blockquotes
 * - --- horizontal rules
 */

import React from 'react';
import { Text, Box } from 'ink';
import { theme } from '../colors.js';

interface MarkdownTextProps {
  children: string;
}

interface Segment {
  type: 'text' | 'bold' | 'italic' | 'code' | 'boldItalic';
  content: string;
}

/**
 * Parse inline markdown within a line
 */
function parseInline(text: string): Segment[] {
  const segments: Segment[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    // Bold italic ***text***
    let match = remaining.match(/^\*\*\*(.+?)\*\*\*/);
    if (match) {
      segments.push({ type: 'boldItalic', content: match[1] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // Bold **text**
    match = remaining.match(/^\*\*(.+?)\*\*/);
    if (match) {
      segments.push({ type: 'bold', content: match[1] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // Italic *text*
    match = remaining.match(/^\*([^*]+?)\*/);
    if (match) {
      segments.push({ type: 'italic', content: match[1] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // Inline code `text`
    match = remaining.match(/^`([^`]+)`/);
    if (match) {
      segments.push({ type: 'code', content: match[1] });
      remaining = remaining.slice(match[0].length);
      continue;
    }

    // Regular character
    const lastSeg = segments[segments.length - 1];
    if (lastSeg && lastSeg.type === 'text') {
      lastSeg.content += remaining[0];
    } else {
      segments.push({ type: 'text', content: remaining[0] });
    }
    remaining = remaining.slice(1);
  }

  return segments;
}

/**
 * Render inline segments
 */
const InlineLine: React.FC<{ text: string }> = ({ text }) => {
  const segments = parseInline(text);

  return (
    <Text wrap="wrap">
      {segments.map((seg, i) => {
        switch (seg.type) {
          case 'bold':
            return <Text key={i} bold color={theme.text.primary}>{seg.content}</Text>;
          case 'italic':
            return <Text key={i} italic color={theme.text.primary}>{seg.content}</Text>;
          case 'boldItalic':
            return <Text key={i} bold italic color={theme.text.primary}>{seg.content}</Text>;
          case 'code':
            return <Text key={i} color={theme.status.info}>{seg.content}</Text>;
          default:
            return <Text key={i} color={theme.text.primary}>{seg.content}</Text>;
        }
      })}
    </Text>
  );
};

export const MarkdownText: React.FC<MarkdownTextProps> = ({ children }) => {
  const lines = children.split('\n');
  const elements: React.ReactNode[] = [];

  let inCodeBlock = false;
  let codeLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Code block delimiter
    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeLines = [];
      } else {
        // End code block - render accumulated lines
        elements.push(
          <Box key={`code-${i}`} flexDirection="column">
            {codeLines.map((cl, j) => (
              <Text key={j} color={theme.status.success}>{cl}</Text>
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

    // Horizontal rule
    if (/^-{3,}$/.test(line.trim())) {
      elements.push(<Text key={`hr-${i}`} color={theme.text.muted}>───</Text>);
      continue;
    }

    // Heading (# text, ## text, etc.)
    const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      elements.push(
        <Text key={`h-${i}`} bold color={theme.text.primary}>{headingMatch[2]}</Text>
      );
      continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      elements.push(
        <Text key={`q-${i}`} color={theme.text.muted} italic>{line.slice(2)}</Text>
      );
      continue;
    }

    // List item
    const listMatch = line.match(/^(\s*)[-*]\s+(.+)$/);
    if (listMatch) {
      elements.push(
        <Box key={`li-${i}`} flexDirection="row">
          <Text color={theme.status.warning}>{listMatch[1]}- </Text>
          <InlineLine text={listMatch[2]} />
        </Box>
      );
      continue;
    }

    // Regular line
    elements.push(
      <Box key={`l-${i}`}>
        <InlineLine text={line} />
      </Box>
    );
  }

  // Handle unclosed code block
  if (inCodeBlock && codeLines.length > 0) {
    elements.push(
      <Box key="code-end" flexDirection="column">
        {codeLines.map((cl, j) => (
          <Text key={j} color={theme.status.success}>{cl}</Text>
        ))}
      </Box>
    );
  }

  return <Box flexDirection="column">{elements}</Box>;
};
