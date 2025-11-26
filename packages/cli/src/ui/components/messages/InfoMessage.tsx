/**
 * Info Message Component
 * Reference: Gemini CLI ui/components/messages/InfoMessage.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { InfoHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface InfoMessageProps {
  item: InfoHistoryItem;
}

export const InfoMessage: React.FC<InfoMessageProps> = ({ item }) => {
  const prefix = 'ℹ ';
  const prefixWidth = prefix.length;

  return (
    <Box flexDirection="row" marginBottom={1}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.message.system}>{prefix}</Text>
      </Box>
      <Box flexGrow={1}>
        <Text wrap="wrap" color={theme.message.system}>
          {item.message}
        </Text>
      </Box>
    </Box>
  );
};
