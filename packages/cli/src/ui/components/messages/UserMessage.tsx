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
  terminalWidth?: number;
}

export const UserMessage: React.FC<UserMessageProps> = ({ item, terminalWidth }) => {
  const prefix = '> ';
  const prefixWidth = prefix.length;
  const isSlashCommand = item.text.startsWith('/');

  // Use message.user color for user messages (distinct from assistant text)
  const textColor = isSlashCommand ? theme.text.accent : theme.message.user;

  return (
    <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
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
