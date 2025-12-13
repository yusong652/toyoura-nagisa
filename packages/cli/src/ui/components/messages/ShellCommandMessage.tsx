/**
 * Shell Command Message Component
 * Displays user shell commands (! prefix) with distinct styling
 */

import React from 'react';
import { Box, Text } from 'ink';
import type { ShellCommandHistoryItem } from '../../types.js';
import { theme, colors } from '../../colors.js';

interface ShellCommandMessageProps {
  item: ShellCommandHistoryItem;
  terminalWidth?: number;
}

export const ShellCommandMessage: React.FC<ShellCommandMessageProps> = ({ item, terminalWidth }) => {
  const prefix = '! ';

  return (
    <Box marginBottom={1} width={terminalWidth}>
      <Text backgroundColor={colors.bgLight}>
        <Text color={theme.status.warning} bold>{prefix}</Text>
        <Text color={theme.status.warning}>{item.command}</Text>
      </Text>
    </Box>
  );
};
