/**
 * Assistant Message Component
 * Reference: Gemini CLI ui/components/messages/GeminiMessage.tsx
 *
 * Displays AI assistant responses with Nagisa's ball icon (⏺) prefix.
 * The white ball represents Nagisa's round body shape.
 * Supports text and thinking content blocks.
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import type { AssistantHistoryItem, ContentBlock } from '../../types.js';
import { theme } from '../../colors.js';
import { getCachedStringWidth } from '../../utils/textUtils.js';

// Maximum lines for thinking blocks (shows last N lines when exceeded)
const MAX_THINKING_LINES = 8;

interface AssistantMessageProps {
  item: AssistantHistoryItem;
  terminalWidth?: number;
}

/**
 * Get the last N lines of content, showing most recent thinking
 */
function getLastLines(content: string, maxLines: number): { text: string; truncated: boolean } {
  const lines = content.split('\n');
  if (lines.length <= maxLines) {
    return { text: content, truncated: false };
  }
  return {
    text: lines.slice(-maxLines).join('\n'),
    truncated: true,
  };
}

const renderContentBlock = (block: ContentBlock, index: number, isStreaming: boolean): React.ReactNode => {
  switch (block.type) {
    case 'text': {
      // Trim whitespace for display (some LLM APIs add leading/trailing newlines)
      const displayText = block.text.trim();
      return (
        <Box key={`text-${index}`} flexDirection="row">
          <Text wrap="wrap" color={theme.text.primary}>
            {displayText}
          </Text>
          {/* Show cursor when streaming and this is the last text block */}
          {isStreaming && (
            <Text color={theme.text.muted}>▌</Text>
          )}
        </Box>
      );
    }

    case 'thinking': {
      // Trim and limit thinking content to last N lines (auto-scroll effect)
      const { text, truncated } = getLastLines(block.thinking.trim(), MAX_THINKING_LINES);
      return (
        <Box key={`thinking-${index}`} flexDirection="column">
          {truncated && (
            <Text color={theme.text.muted}>...</Text>
          )}
          <Text color={theme.message.thinking} dimColor wrap="wrap">
            {text}
          </Text>
        </Box>
      );
    }

    default:
      return null;
  }
};

export const AssistantMessage: React.FC<AssistantMessageProps> = ({ item, terminalWidth }) => {
  // Use ⏺ (white ball) prefix - represents Nagisa's round body shape
  const prefix = '⏺ ';
  const prefixWidth = getCachedStringWidth(prefix);

  // Filter to get only text blocks for streaming indicator logic
  const textBlocks = item.content.filter((b): b is ContentBlock & { type: 'text' } => b.type === 'text');
  const hasTextContent = textBlocks.length > 0 && textBlocks.some(b => b.text.length > 0);

  // Find last text block index (ES5 compatible)
  let lastTextBlockIndex = -1;
  for (let i = item.content.length - 1; i >= 0; i--) {
    if (item.content[i].type === 'text') {
      lastTextBlockIndex = i;
      break;
    }
  }

  return (
    <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.text.accent}>{prefix}</Text>
      </Box>
      <Box flexGrow={1} flexDirection="column">
        {item.content.map((block, index) => {
          // Only show streaming cursor on the last text block
          const isLastTextBlock = block.type === 'text' && index === lastTextBlockIndex;
          return renderContentBlock(block, index, item.isStreaming === true && isLastTextBlock);
        })}
        {/* Show spinner when streaming but no content yet */}
        {item.isStreaming && !hasTextContent && (
          <Text color={theme.ui.spinner}>
            <Spinner type="dots" />
          </Text>
        )}
      </Box>
    </Box>
  );
};
