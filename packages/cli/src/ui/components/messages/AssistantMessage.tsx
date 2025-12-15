/**
 * Assistant Message Component
 * Reference: Gemini CLI ui/components/messages/GeminiMessage.tsx
 *
 * Displays AI assistant responses with Nagisa's filled circle (●) prefix.
 * The filled circle represents Nagisa's round body shape.
 * Supports text and thinking content blocks.
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import type { AssistantHistoryItem, ContentBlock } from '../../types.js';
import { theme } from '../../colors.js';
import { getCachedStringWidth } from '../../utils/textUtils.js';
import { MarkdownText } from '../MarkdownText.js';
import { useAppState } from '../../contexts/AppStateContext.js';

// Maximum lines for thinking blocks (shows last N lines when exceeded)
// Keep in sync with PendingItemDisplay.tsx for consistent display
const MAX_THINKING_LINES = 4;
// No limit when in full context mode
const MAX_THINKING_LINES_FULL = Infinity;

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

const renderContentBlock = (
  block: ContentBlock,
  index: number,
  isStreaming: boolean,
  maxThinkingLines: number,
): React.ReactNode => {
  switch (block.type) {
    case 'text': {
      // Trim whitespace for display (some LLM APIs add leading/trailing newlines)
      const displayText = block.text.trim();
      return (
        <Box key={`text-${index}`} flexDirection="row">
          <MarkdownText>{displayText}</MarkdownText>
          {/* Show cursor when streaming and this is the last text block */}
          {isStreaming && (
            <Text color={theme.text.muted}>▌</Text>
          )}
        </Box>
      );
    }

    case 'thinking': {
      // Trim and limit thinking content to last N lines (auto-scroll effect)
      const { text, truncated } = getLastLines(block.thinking.trim(), maxThinkingLines);
      return (
        <Box key={`thinking-${index}`} flexDirection="column">
          {truncated && (
            <Text color={theme.text.muted}>...</Text>
          )}
          <MarkdownText dimColor baseColor={theme.message.thinking}>
            {text}
          </MarkdownText>
        </Box>
      );
    }

    default:
      return null;
  }
};

export const AssistantMessage: React.FC<AssistantMessageProps> = ({ item, terminalWidth }) => {
  const { isFullContextMode } = useAppState();

  // Use ● (filled circle) prefix - represents Nagisa's round body shape
  const prefix = '● ';
  const prefixWidth = getCachedStringWidth(prefix);

  // Determine max lines for thinking blocks based on mode
  const maxThinkingLines = isFullContextMode ? MAX_THINKING_LINES_FULL : MAX_THINKING_LINES;

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
        <Text color={theme.text.primary}>{prefix}</Text>
      </Box>
      <Box flexGrow={1} flexDirection="column">
        {item.content.map((block, index) => {
          // Only show streaming cursor on the last text block
          const isLastTextBlock = block.type === 'text' && index === lastTextBlockIndex;
          return renderContentBlock(block, index, item.isStreaming === true && isLastTextBlock, maxThinkingLines);
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
