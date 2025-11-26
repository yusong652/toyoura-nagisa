/**
 * Thinking Message Component
 * Displays AI thinking/reasoning content
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ThinkingHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface ThinkingMessageProps {
  item: ThinkingHistoryItem;
}

export const ThinkingMessage: React.FC<ThinkingMessageProps> = ({ item }) => {
  const prefix = '~ ';
  const prefixWidth = prefix.length;

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
