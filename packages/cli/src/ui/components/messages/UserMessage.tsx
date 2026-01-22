/**
 * User Message Component
 * Reference: Gemini CLI ui/components/messages/UserMessage.tsx
 *
 * Uses background panel styling to distinguish from assistant messages.
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { UserHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';
import { MarkdownText } from '../MarkdownText.js';
import { PanelSection } from '../shared/PanelSection.js';

interface UserMessageProps {
  item: UserHistoryItem;
  terminalWidth?: number;
}

export const UserMessage: React.FC<UserMessageProps> = ({ item, terminalWidth }) => {
  // Use "> " (> + 1 space) to align with assistant message prefix "● " (width 2)
  const prefix = '> ';
  const prefixWidth = prefix.length;
  const userColor = theme.text.primary;

  return (
    <Box marginBottom={1} width={terminalWidth}>
      <PanelSection paddingX={1} width={terminalWidth}>
        <Box flexDirection="row">
          <Box width={prefixWidth} flexShrink={0}>
            <Text color={userColor} bold>
              {prefix}
            </Text>
          </Box>
          <Box flexGrow={1}>
            <MarkdownText baseColor={userColor}>{item.text.trim()}</MarkdownText>
          </Box>
        </Box>
      </PanelSection>
    </Box>
  );
};
