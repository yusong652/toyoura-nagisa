/**
 * Assistant Message Component
 * Reference: Gemini CLI ui/components/messages/GeminiMessage.tsx
 *
 * Displays AI assistant responses with the ✦ prefix like Gemini CLI.
 * Supports text and thinking content blocks.
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import type { AssistantHistoryItem, ContentBlock } from '../../types.js';
import { theme } from '../../colors.js';

interface AssistantMessageProps {
  item: AssistantHistoryItem;
  terminalWidth?: number;
}

const renderContentBlock = (block: ContentBlock, index: number, isStreaming: boolean): React.ReactNode => {
  switch (block.type) {
    case 'text': {
      // Trim whitespace for display (some LLM APIs add leading/trailing newlines)
      const displayText = block.text.trim();
      return (
        <Box key={index} flexDirection="row">
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
      // Trim whitespace for display (some LLM APIs add leading/trailing newlines)
      const displayThinking = block.thinking.trim();
      return (
        <Box key={index}>
          <Text color={theme.message.thinking} dimColor wrap="wrap">
            {displayThinking}
          </Text>
        </Box>
      );
    }

    default:
      return null;
  }
};

export const AssistantMessage: React.FC<AssistantMessageProps> = ({ item, terminalWidth }) => {
  // Use ✦ prefix like Gemini CLI
  const prefix = '✦ ';
  const prefixWidth = 2; // Unicode character width

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
