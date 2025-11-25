/**
 * Assistant Message Component
 * Reference: Gemini CLI ui/components/messages/GeminiMessage.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import Spinner from 'ink-spinner';
import type { AssistantHistoryItem, ContentBlock } from '../../types.js';
import { theme } from '../../colors.js';

interface AssistantMessageProps {
  item: AssistantHistoryItem;
}

const renderContentBlock = (block: ContentBlock, index: number): React.ReactNode => {
  switch (block.type) {
    case 'text':
      return (
        <Text key={index} wrap="wrap">
          {block.text}
        </Text>
      );

    case 'thinking':
      return (
        <Box key={index} marginY={1}>
          <Text color={theme.message.thinking} dimColor>
            {block.thinking}
          </Text>
        </Box>
      );

    default:
      return null;
  }
};

export const AssistantMessage: React.FC<AssistantMessageProps> = ({ item }) => {
  // Use simple symbol prefix like Gemini CLI
  const prefix = '* ';
  const prefixWidth = prefix.length;

  return (
    <Box flexDirection="row" marginY={1}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.text.accent}>{prefix}</Text>
      </Box>
      <Box flexGrow={1} flexDirection="column">
        {item.content.map((block, index) => renderContentBlock(block, index))}
        {item.isStreaming && (
          <Text color={theme.ui.spinner}>
            <Spinner type="dots" />
          </Text>
        )}
      </Box>
    </Box>
  );
};
