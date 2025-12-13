/**
 * Shell Command Message Component
 * Displays user shell commands (! prefix) with distinct styling
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ShellCommandHistoryItem } from '../../types.js';
import { theme } from '../../colors.js';

interface ShellCommandMessageProps {
  item: ShellCommandHistoryItem;
  terminalWidth?: number;
}

export const ShellCommandMessage: React.FC<ShellCommandMessageProps> = ({ item, terminalWidth }) => {
  const prefix = '! ';
  const prefixWidth = prefix.length;

  return (
    <Box flexDirection="row" marginBottom={1} width={terminalWidth}>
      <Box width={prefixWidth} flexShrink={0}>
        <Text color={theme.status.warning} bold>{prefix}</Text>
      </Box>
      <Box flexGrow={1}>
        <Text wrap="wrap" color={theme.status.warning}>
          {item.command}
        </Text>
      </Box>
    </Box>
  );
};
