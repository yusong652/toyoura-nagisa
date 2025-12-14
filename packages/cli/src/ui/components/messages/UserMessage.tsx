/**
 * User Message Component
 * Reference: Gemini CLI ui/components/messages/UserMessage.tsx
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
  // Use ">  " (> + 2 spaces) to align with assistant message prefix "⏺ " (width 3)
  const prefix = '>  ';
  const prefixWidth = prefix.length;
  const isSlashCommand = item.text.startsWith('/');

  // Slash commands don't need markdown rendering
  if (isSlashCommand) {
    return (
      <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
        <Box width={prefixWidth} flexShrink={0}>
          <Text color={theme.text.accent}>{prefix}</Text>
        </Box>
        <Box flexGrow={1}>
          <Text wrap="wrap" color={theme.text.accent}>
            {item.text}
          </Text>
        </Box>
      </Box>
    );
  }

  return (
    <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.text.accent}>{prefix}</Text>
      </Box>
      <Box flexGrow={1}>
        <MarkdownText baseColor={theme.text.accent}>{item.text}</MarkdownText>
      </Box>
    </Box>
  );
};
