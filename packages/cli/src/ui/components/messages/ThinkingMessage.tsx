/**
 * Thinking Message Component
 * Displays AI thinking/reasoning content with Nagisa's ball icon
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ThinkingHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface ThinkingMessageProps {
  item: ThinkingHistoryItem;
}

export const ThinkingMessage: React.FC<ThinkingMessageProps> = ({ item }) => {
  // Use ⏺ (ball) prefix - same as AssistantMessage, represents Nagisa
  const prefix = '⏺ ';
  const prefixWidth = 2; // Unicode character width

  return (
    <Box flexDirection="row" marginBottom={1}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.message.thinking}>{prefix}</Text>
      </Box>
      <Box flexGrow={1}>
        <Text wrap="wrap" color={theme.message.thinking} dimColor>
          {item.thinking}
        </Text>
      </Box>
    </Box>
  );
};
