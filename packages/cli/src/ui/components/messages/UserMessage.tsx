/**
 * User Message Component
 * Reference: Gemini CLI ui/components/messages/UserMessage.tsx
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { UserHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface UserMessageProps {
  item: UserHistoryItem;
}

export const UserMessage: React.FC<UserMessageProps> = ({ item }) => {
  const prefix = '> ';
  const prefixWidth = prefix.length;
  const isSlashCommand = item.text.startsWith('/');

  const textColor = isSlashCommand ? theme.text.accent : theme.text.secondary;

  return (
    <Box flexDirection="row" marginBottom={1}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.text.accent}>{prefix}</Text>
      </Box>
      <Box flexGrow={1}>
        <Text wrap="wrap" color={textColor}>
          {item.text}
        </Text>
      </Box>
    </Box>
  );
};
