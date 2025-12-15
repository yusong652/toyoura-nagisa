/**
 * User Message Component
 * Reference: Gemini CLI ui/components/messages/UserMessage.tsx
 *
 * Uses blue/cyan color to distinguish from assistant messages.
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { UserHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { MarkdownText } from '../MarkdownText.js';

interface UserMessageProps {
  item: UserHistoryItem;
  terminalWidth?: number;
}

export const UserMessage: React.FC<UserMessageProps> = ({ item, terminalWidth }) => {
  // Use "> " (> + 1 space) to align with assistant message prefix "● " (width 2)
  const prefix = '> ';
  const prefixWidth = prefix.length;
  // Use theme.message.user (blue/cyan) for user messages
  const userColor = theme.message.user;

  return (
    <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={userColor} bold>{prefix}</Text>
      </Box>
      <Box flexGrow={1}>
        <MarkdownText baseColor={userColor}>{item.text}</MarkdownText>
      </Box>
    </Box>
  );
};
